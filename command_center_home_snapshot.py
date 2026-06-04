from __future__ import annotations

import datetime as _dt
import json
from collections.abc import Mapping
from numbers import Number
from pathlib import Path
from typing import Any

import command_center_facts_packet as facts_packet_service
import command_center_radar_packet as radar_packet_service
import command_center_etf_packet as etf_packet_service
import command_center_discipline_packet as discipline_packet_service
import command_center_data_gap_report as data_gap_report_service
import command_center_market_packet as market_packet_service
import command_center_quant_packet as quant_packet_service
import command_center_chip_packet as chip_packet_service
import command_center_moneyflow_packet as moneyflow_packet_service
import command_center_dragon_tiger_packet as dragon_tiger_packet_service
import command_center_margin_packet as margin_packet_service
import command_center_limit_emotion_packet as limit_emotion_packet_service
import command_center_hard_risk_packet as hard_risk_packet_service
import command_center_market_profile_summary as market_profile_summary_service
import command_center_evidence_summary as evidence_summary_service
import command_center_data_issue_explainer as data_issue_explainer_service
import command_center_data_capability_console as data_capability_console_service
import command_center_data_health_ledger as data_health_ledger_service
import command_center_a_share_capability_matrix as a_share_capability_matrix_service
import command_center_legacy_a_share_debug_summary as legacy_a_share_debug_summary_service
import command_center_legacy_a_share_gate as legacy_a_share_gate_service
import command_center_legacy_migration_map as legacy_migration_map_service
import command_center_loop_status as loop_status_service
import market_data_capability as data_capability_service


CACHE_DIR_NAME = ".stock_ming_cache"
SNAPSHOT_FILENAME = "command_center_latest.json"
SNAPSHOT_SOURCE = "command_center_home_snapshot"
MAX_CANDIDATES = 3
MAX_ERRORS = 8
MAX_CAPABILITY_ITEMS = 8

DATA_HEALTH_TIMELINE_RECOVERY_EVENTS = {
    "last_failure",
    "manual_required",
    "cache_used",
    "empty_recent",
    "needs_check",
}

DATA_HEALTH_TIMELINE_RECOVERY_PRIORITY = {
    "last_failure": 1,
    "manual_required": 2,
    "cache_used": 3,
    "empty_recent": 3,
    "needs_check": 4,
}

A_SHARE_FACT_RECOVERY_SOURCES = (
    {
        "key": "moneyflow",
        "label": "个股资金流",
        "packet_key": "moneyflow_packet",
        "writes_packet": "command_center_moneyflow_packet",
        "source_fallback": "Tushare moneyflow",
    },
    {
        "key": "dragon_tiger",
        "label": "龙虎榜",
        "packet_key": "dragon_tiger_packet",
        "writes_packet": "command_center_dragon_tiger_packet",
        "source_fallback": "Tushare top_list/top_inst",
    },
    {
        "key": "margin",
        "label": "融资融券",
        "packet_key": "margin_packet",
        "writes_packet": "command_center_margin_packet",
        "source_fallback": "Tushare margin_detail",
    },
    {
        "key": "limit_emotion",
        "label": "涨跌停/情绪",
        "packet_key": "limit_emotion_packet",
        "writes_packet": "command_center_limit_emotion_packet",
        "source_fallback": "Tushare stk_limit/limit_list_d/limit_cpt_list",
    },
    {
        "key": "chip_radar",
        "label": "筹码/胜率",
        "packet_key": "chip_packet",
        "writes_packet": "command_center_chip_packet",
        "source_fallback": "Tushare cyq_perf/cyq_chips",
    },
)

LEGACY_A_SHARE_GAP_KEYS = {"limit_emotion", "chip_radar"}

LEGACY_A_SHARE_GAP_DIAGNOSTICS = {
    "limit_emotion": {
        "why_not_found": (
            "Tushare 之前拉满不等于今天一定可见；常见原因是当日数据尚未发布、"
            "limit_cpt_list 权限不足、本会话已跳过重复请求，或最近交易日没有可验证涨跌停/情绪覆盖。"
        ),
        "manual_recovery_steps": [
            "进入高级工具箱 / 数据源体检",
            "点击“手动检测涨跌停/情绪”",
            "成功后写回 command_center_limit_emotion_packet，再回到综合中心复核交易日和来源",
        ],
        "button_context": "只检测 stk_limit / limit_list_d / limit_cpt_list；不触发 DeepSeek、回测或全市场扫描。",
        "decision_guardrail": "缺少涨跌停/情绪时，不能确认题材温度、追高边界或涨跌停风险。",
    },
    "chip_radar": {
        "why_not_found": (
            "筹码/胜率可能因为 cyq_perf 或 cyq_chips 权限、标的覆盖、交易日更新节奏、"
            "近期无数据或缓存过期而不可见；这不是胜率安全，也不是没有压力位。"
        ),
        "manual_recovery_steps": [
            "进入高级工具箱 / 量化推演",
            "点击“手动检测筹码/胜率”",
            "成功后写回 command_center_chip_packet，再回到综合中心检查筹码压力和胜率口径",
        ],
        "button_context": "只检测 cyq_perf / cyq_chips；不触发 DeepSeek、回测或全市场扫描。",
        "decision_guardrail": "缺少筹码/胜率时，不能把压力位、获利盘或历史胜率写成已验证依据。",
    },
}

LEGACY_A_SHARE_GAP_WRITES_TO_KEY = {
    "command_center_limit_emotion_packet": "limit_emotion",
    "command_center_chip_packet": "chip_radar",
}

RECOVERY_WRITES_PACKET_TO_SNAPSHOT_KEY = {
    "command_center_radar_packet": "radar_packet",
    "command_center_etf_packet": "etf_packet",
    "command_center_discipline_packet": "discipline_packet",
    "command_center_quant_packet": "quant_packet",
    "command_center_chip_packet": "chip_packet",
    "command_center_moneyflow_packet": "moneyflow_packet",
    "command_center_dragon_tiger_packet": "dragon_tiger_packet",
    "command_center_margin_packet": "margin_packet",
    "command_center_limit_emotion_packet": "limit_emotion_packet",
    "command_center_hard_risk_packet": "hard_risk_packet",
    "command_center_market_packet": "market_packet",
}

OLD_WORKSPACE_API_TO_WRITES_PACKET = {
    "moneyflow": "command_center_moneyflow_packet",
    "top_list": "command_center_dragon_tiger_packet",
    "top_inst": "command_center_dragon_tiger_packet",
    "margin_detail": "command_center_margin_packet",
    "stk_limit": "command_center_limit_emotion_packet",
    "limit_list_d": "command_center_limit_emotion_packet",
    "limit_cpt_list": "command_center_limit_emotion_packet",
    "cyq_perf": "command_center_chip_packet",
    "cyq_chips": "command_center_chip_packet",
    "akshare_manual_refresh": "command_center_data_capability_packet",
    "yfinance_market_data": "command_center_data_capability_packet",
    "brain_memory": "command_center_data_capability_packet",
}

PROVIDER_CAPABILITY_COCKPIT_CONFIG = {
    "Tushare": {
        "label": "Tushare",
        "role": "A股专业数据",
        "legacy_tab": "数据源体检",
        "action_label": "手动检测 Tushare 专业接口",
        "next_action": "优先处理权限/积分、本会话跳过和近期无记录；不要把缺口当成行情不存在。",
    },
    "AkShare": {
        "label": "AkShare",
        "role": "A股补充/重型刷新",
        "legacy_tab": "数据源体检",
        "action_label": "手动刷新 AkShare",
        "next_action": "仅在需要时手动刷新；页面打开不会自动跑 AkShare 重型接口。",
    },
    "yfinance": {
        "label": "yfinance",
        "role": "美股/全球行情补充",
        "legacy_tab": "数据源体检",
        "action_label": "手动检测 yfinance",
        "next_action": "手动检测美股/全球行情；不要用 A股口径替代美股数据。",
    },
    "Supabase": {
        "label": "Supabase",
        "role": "云端外脑/记忆",
        "legacy_tab": "云端外脑",
        "action_label": "检查 Supabase 配置",
        "next_action": "检查本地配置和连接状态；云端外脑缺失不影响本地结构化决策链。",
    },
}

SENSITIVE_KEY_PARTS = (
    "api_key",
    "apikey",
    "secret",
    "password",
    "access_token",
    "refresh_token",
    "auth_token",
    "bearer",
    "deepseek_prompt",
    "raw_prompt",
    "prompt_text",
    "system_prompt",
    "user_prompt",
)

MODULE_LABELS = {
    "market": "市场",
    "quant": "量化",
    "discipline": "纪律",
    "margin_etf": "融资 ETF",
    "next_ticket": "下一票",
    "strategy_execution": "策略执行",
}

DATA_GAP_LABELS = {
    **MODULE_LABELS,
    "decision": "今日总决策",
}

CAPABILITY_RESTRICTED_STATES = {"permission_denied", "disabled_this_session", "not_configured", "network_failed", "failed"}
CAPABILITY_PENDING_STATES = {"empty_recent", "stale_cache", "fallback_used", "requires_manual_refresh", "unknown"}


def _as_mapping(value: Any) -> dict:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _as_list(value: Any) -> list:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return []


def _to_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip() or default
    if isinstance(value, (bool, Number)):
        return str(value)
    return str(value).strip() or default


def _to_number(value: Any) -> int | float | None:
    if value in [None, ""]:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, Number):
        return value
    if isinstance(value, str):
        text = value.strip().replace(",", "").replace("¥", "").replace("￥", "").replace("%", "")
        if not text or text in {"暂无", "None", "nan", "--"}:
            return None
        try:
            number = float(text)
            return int(number) if number.is_integer() else number
        except Exception:
            return None
    return None


def _now_iso(now: Any = None) -> str:
    if isinstance(now, _dt.datetime):
        return now.isoformat(timespec="seconds")
    if isinstance(now, _dt.date):
        return _dt.datetime.combine(now, _dt.time.min).isoformat(timespec="seconds")
    if isinstance(now, str) and now.strip():
        return now.strip()
    return _dt.datetime.now().isoformat(timespec="seconds")


def _today_string(today: Any = None) -> str:
    if isinstance(today, _dt.datetime):
        return today.date().isoformat()
    if isinstance(today, _dt.date):
        return today.isoformat()
    if isinstance(today, str) and len(today) >= 10:
        return today[:10]
    return _dt.date.today().isoformat()


def _is_sensitive_key(key: Any) -> bool:
    text = str(key or "").lower()
    return any(part in text for part in SENSITIVE_KEY_PARTS)


def sanitize_snapshot_payload(value: Any) -> Any:
    if isinstance(value, Mapping):
        clean = {}
        for key, item in value.items():
            if _is_sensitive_key(key):
                continue
            clean[str(key)] = sanitize_snapshot_payload(item)
        return clean
    if isinstance(value, (list, tuple, set)):
        return [sanitize_snapshot_payload(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return _to_text(value)


def get_home_snapshot_path(base_dir: str | Path | None = None) -> Path:
    root = Path(base_dir) if base_dir is not None else Path.cwd()
    return root / CACHE_DIR_NAME / SNAPSHOT_FILENAME


def _empty_snapshot(reason: str = "暂无可执行候选。点击刷新今日基础数据生成。") -> dict:
    snapshot = {
        "status": "empty",
        "is_empty": True,
        "timestamp": "",
        "source": SNAPSHOT_SOURCE,
        "decision_packet": {},
        "strategy_packet": {},
        "today_action": {
            "overall_action": "等待",
            "risk_level": "中",
            "market_bias": "未刷新",
            "position_mode": "空仓等待",
            "margin_mode": "不使用融资",
        },
        "holding_action": {
            "ticker": "",
            "name": "",
            "investment_horizon": "",
            "cost": None,
            "shares": None,
            "current_price": None,
            "floating_pnl": None,
            "floating_pnl_text": "暂无",
            "action_state": "待刷新",
            "add_condition": "等待量化、纪律和市场至少两项同向后再考虑。",
            "reduce_condition": "触发止损、减仓或风险预算失效时优先降低暴露。",
            "invalidation_condition": "市场环境转弱或纪律信号反向时，本轮建议失效。",
        },
        "next_ticket_candidates": [],
        "radar_packet": radar_packet_service.build_command_center_radar_packet({}),
        "etf_packet": etf_packet_service.build_command_center_etf_packet({}),
        "discipline_packet": discipline_packet_service.build_command_center_discipline_packet({}),
        "quant_packet": quant_packet_service.build_command_center_quant_packet({}),
        "chip_packet": chip_packet_service.build_command_center_chip_packet({}),
        "moneyflow_packet": moneyflow_packet_service.build_command_center_moneyflow_packet({}),
        "dragon_tiger_packet": dragon_tiger_packet_service.build_command_center_dragon_tiger_packet({}),
        "margin_packet": margin_packet_service.build_command_center_margin_packet({}),
        "limit_emotion_packet": limit_emotion_packet_service.build_command_center_limit_emotion_packet({}),
        "hard_risk_packet": hard_risk_packet_service.build_command_center_hard_risk_packet({}),
        "market_profile_evidence": market_profile_summary_service.build_market_profile_evidence_strip(),
        "margin_etf_summary": {
            "current_margin_ratio": None,
            "recommended_margin_ratio": None,
            "recommended_cash_ratio": None,
            "today_main_direction": "待刷新",
            "recommended_etfs": [],
            "watch_not_chase": ["暂无 ETF 快照；不追高，等待刷新后再判断。"],
        },
        "risk_alerts": {
            "must_not_do": ["不追高", "不满仓", "不在未刷新数据下加融资"],
            "reduce_conditions": [],
            "data_gaps": [reason],
            "uses_cache": False,
        },
        "data_coverage": {key: "missing" for key in DATA_GAP_LABELS},
        "data_freshness": {
            "state": "missing",
            "label": "待刷新",
            "last_updated": "暂无",
            "deepseek_called": False,
        },
        "data_capability": build_data_capability_snapshot({}),
        "a_share_capability_matrix": a_share_capability_matrix_service.build_a_share_capability_matrix(),
        "facts_packet": facts_packet_service.build_command_center_facts_packet({}),
        "data_gap_report": data_gap_report_service.build_command_center_data_gap_report(),
        "data_issue_explainer": data_issue_explainer_service.build_data_issue_explainer_packet(),
        "data_capability_console": data_capability_console_service.build_data_capability_console_packet(),
        "a_share_user_data_diagnostic": legacy_a_share_debug_summary_service.build_user_data_diagnostic_view_model(),
        "data_recovery_actions": [],
        "legacy_a_share_fact_recovery_actions": [],
        "tool_recovery_actions": [],
        "next_ticket_evidence_recovery_actions": [],
        "data_recovery_center": build_home_data_recovery_center(),
        "legacy_migration_map": legacy_migration_map_service.build_legacy_migration_map(),
        "old_workspace_packet_bridge": build_old_workspace_packet_bridge(),
        "latest_recovery_result_notice": {},
        "recovery_result_status_strip": build_recovery_result_status_strip(),
        "command_center_recovery_result_timeline": build_recovery_result_timeline(),
        "recovery_result_timeline": build_recovery_result_timeline(),
        "market_packet": market_packet_service.build_command_center_market_packet({}),
        "errors": [],
        "empty_message": reason,
        "deepseek_called": False,
    }
    snapshot["a_share_fact_recovery_summary"] = build_a_share_fact_recovery_summary(snapshot)
    snapshot["a_share_evidence_recovery_ledger"] = build_a_share_evidence_recovery_ledger(snapshot)
    snapshot["strategy_prerequisite_recovery_ledger"] = build_strategy_prerequisite_recovery_ledger(snapshot)
    snapshot["legacy_a_share_gap_summary"] = build_legacy_a_share_gap_summary(snapshot)
    snapshot["old_workspace_data_absence_ledger"] = build_old_workspace_data_absence_ledger(snapshot)
    snapshot["a_share_evidence_packet"] = evidence_summary_service.build_a_share_evidence_radar_view_model(snapshot)
    snapshot["command_center_evidence_radar_packet"] = snapshot["a_share_evidence_packet"]
    snapshot["data_health_ledger"] = _as_mapping(_as_mapping(snapshot.get("data_capability_console")).get("data_health_ledger"))
    snapshot["data_health_visibility_summary"] = data_health_ledger_service.build_data_health_visibility_summary(
        snapshot["data_health_ledger"]
    )
    snapshot["command_center_data_health_visibility_summary"] = snapshot["data_health_visibility_summary"]
    snapshot["data_health_timeline"] = data_health_ledger_service.build_data_health_timeline(snapshot["data_health_ledger"])
    snapshot["command_center_data_health_timeline"] = snapshot["data_health_timeline"]
    snapshot["data_health_timeline_recovery_actions"] = build_data_health_timeline_recovery_actions(
        snapshot["data_health_timeline"]
    )
    snapshot["command_center_data_health_timeline_recovery_actions"] = snapshot["data_health_timeline_recovery_actions"]
    snapshot["provider_data_capability_cockpit"] = build_provider_data_capability_cockpit(snapshot)
    snapshot["data_recovery_center"] = build_home_data_recovery_center(snapshot)
    snapshot = attach_decision_loop_status(snapshot)
    return snapshot


def load_home_action_snapshot(path: str | Path | None = None, base_dir: str | Path | None = None) -> dict:
    snapshot_path = Path(path) if path is not None else get_home_snapshot_path(base_dir)
    if not snapshot_path.exists():
        return _empty_snapshot()
    try:
        payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    except Exception as exc:
        snapshot = _empty_snapshot("本地交易快照读取失败。点击刷新今日基础数据重新生成。")
        snapshot["status"] = "failed"
        snapshot["errors"] = [{"module": "home_snapshot", "message": _to_text(exc), "source": str(snapshot_path), "updated_at": ""}]
        return snapshot
    if not isinstance(payload, Mapping):
        return _empty_snapshot("本地交易快照格式不可用。点击刷新今日基础数据重新生成。")
    snapshot = sanitize_snapshot_payload(payload)
    snapshot.setdefault("source", SNAPSHOT_SOURCE)
    snapshot.setdefault("deepseek_called", False)
    snapshot["is_empty"] = bool(snapshot.get("is_empty"))
    snapshot["data_freshness"] = build_data_freshness(
        snapshot.get("timestamp"),
        snapshot.get("errors"),
        deepseek_called=bool(snapshot.get("deepseek_called")),
    )
    snapshot["data_capability"] = build_data_capability_snapshot(snapshot.get("data_capability") or {})
    snapshot["a_share_capability_matrix"] = a_share_capability_matrix_service.build_a_share_capability_matrix(
        snapshot.get("data_capability") or {},
        snapshot.get("facts_packet") or {},
    )
    snapshot["facts_packet"] = facts_packet_service.build_command_center_facts_packet(
        {"command_center_facts_packet": snapshot.get("facts_packet") or {}}
    )
    snapshot["data_gap_report"] = data_gap_report_service.build_command_center_data_gap_report(
        snapshot.get("data_capability") or {},
        snapshot.get("facts_packet") or {},
        errors=snapshot.get("errors") or [],
    )
    snapshot["data_issue_explainer"] = data_issue_explainer_service.build_data_issue_explainer_packet(
        snapshot.get("data_capability") or {},
        snapshot.get("data_gap_report") or {},
        errors=snapshot.get("errors") or [],
    )
    snapshot["data_capability_console"] = data_capability_console_service.build_data_capability_console_packet(
        snapshot.get("data_capability") or {},
        snapshot.get("data_gap_report") or {},
        data_issue_explainer=snapshot.get("data_issue_explainer") or {},
        errors=snapshot.get("errors") or [],
    )
    snapshot["data_health_ledger"] = _as_mapping(_as_mapping(snapshot.get("data_capability_console")).get("data_health_ledger"))
    snapshot["data_health_visibility_summary"] = data_health_ledger_service.build_data_health_visibility_summary(
        snapshot["data_health_ledger"]
    )
    snapshot["command_center_data_health_visibility_summary"] = snapshot["data_health_visibility_summary"]
    snapshot["data_health_timeline"] = data_health_ledger_service.build_data_health_timeline(snapshot["data_health_ledger"])
    snapshot["command_center_data_health_timeline"] = snapshot["data_health_timeline"]
    snapshot["data_health_timeline_recovery_actions"] = build_data_health_timeline_recovery_actions(
        snapshot["data_health_timeline"]
    )
    snapshot["command_center_data_health_timeline_recovery_actions"] = snapshot["data_health_timeline_recovery_actions"]
    snapshot["provider_data_capability_cockpit"] = build_provider_data_capability_cockpit(snapshot)
    snapshot["a_share_user_data_diagnostic"] = (
        _as_mapping(snapshot.get("a_share_user_data_diagnostic"))
        or legacy_a_share_debug_summary_service.build_user_data_diagnostic_view_model()
    )
    snapshot["data_recovery_actions"] = build_data_recovery_actions_snapshot(snapshot.get("data_capability_console") or {})
    snapshot["market_packet"] = market_packet_service.build_command_center_market_packet(
        {"command_center_market_packet": snapshot.get("market_packet") or {}}
    )
    snapshot["radar_packet"] = radar_packet_service.build_command_center_radar_packet(
        {"command_center_radar_packet": snapshot.get("radar_packet") or {}}
    )
    snapshot["etf_packet"] = etf_packet_service.build_command_center_etf_packet(
        {"command_center_etf_packet": snapshot.get("etf_packet") or {}}
    )
    snapshot["discipline_packet"] = discipline_packet_service.build_command_center_discipline_packet(
        {"command_center_discipline_packet": snapshot.get("discipline_packet") or {}}
    )
    snapshot["quant_packet"] = quant_packet_service.build_command_center_quant_packet(
        {"command_center_quant_packet": snapshot.get("quant_packet") or {}}
    )
    snapshot["chip_packet"] = chip_packet_service.build_command_center_chip_packet(
        {"command_center_chip_packet": snapshot.get("chip_packet") or {}}
    )
    snapshot["moneyflow_packet"] = moneyflow_packet_service.build_command_center_moneyflow_packet(
        {"command_center_moneyflow_packet": snapshot.get("moneyflow_packet") or {}}
    )
    snapshot["dragon_tiger_packet"] = dragon_tiger_packet_service.build_command_center_dragon_tiger_packet(
        {"command_center_dragon_tiger_packet": snapshot.get("dragon_tiger_packet") or {}}
    )
    snapshot["margin_packet"] = margin_packet_service.build_command_center_margin_packet(
        {"command_center_margin_packet": snapshot.get("margin_packet") or {}}
    )
    snapshot["limit_emotion_packet"] = limit_emotion_packet_service.build_command_center_limit_emotion_packet(
        {"command_center_limit_emotion_packet": snapshot.get("limit_emotion_packet") or {}}
    )
    snapshot["hard_risk_packet"] = hard_risk_packet_service.build_command_center_hard_risk_packet(
        {"command_center_hard_risk_packet": snapshot.get("hard_risk_packet") or {}}
    )
    snapshot = attach_margin_etf_evidence_recovery_results(
        attach_next_ticket_evidence_recovery_results(snapshot)
    )
    snapshot["a_share_fact_recovery_summary"] = build_a_share_fact_recovery_summary(snapshot)
    snapshot["a_share_evidence_recovery_ledger"] = build_a_share_evidence_recovery_ledger(snapshot)
    snapshot["strategy_prerequisite_recovery_ledger"] = build_strategy_prerequisite_recovery_ledger(snapshot)
    snapshot["legacy_a_share_gap_summary"] = build_legacy_a_share_gap_summary(snapshot)
    snapshot["old_workspace_data_absence_ledger"] = build_old_workspace_data_absence_ledger(snapshot)
    snapshot["a_share_evidence_packet"] = evidence_summary_service.build_a_share_evidence_radar_view_model(snapshot)
    snapshot["command_center_evidence_radar_packet"] = snapshot["a_share_evidence_packet"]
    snapshot["legacy_a_share_fact_recovery_actions"] = build_legacy_a_share_fact_recovery_actions_snapshot(snapshot)
    snapshot["tool_recovery_actions"] = build_tool_recovery_actions_snapshot(snapshot)
    snapshot["next_ticket_evidence_recovery_actions"] = build_next_ticket_evidence_recovery_actions_snapshot(snapshot)
    snapshot["legacy_migration_map"] = legacy_migration_map_service.build_legacy_migration_map(
        snapshot,
        data_capability_packet=snapshot.get("data_capability") or {},
    )
    snapshot["data_recovery_center"] = build_home_data_recovery_center(snapshot)
    snapshot["old_workspace_packet_bridge"] = build_old_workspace_packet_bridge(snapshot)
    snapshot["latest_recovery_result_notice"] = _as_mapping(snapshot.get("latest_recovery_result_notice"))
    snapshot["recovery_result_status_strip"] = build_recovery_result_status_strip(snapshot)
    snapshot["command_center_recovery_result_timeline"] = build_recovery_result_timeline(
        snapshot,
        latest_notice=snapshot.get("latest_recovery_result_notice") or {},
        status_strip=snapshot.get("recovery_result_status_strip") or {},
    )
    snapshot["recovery_result_timeline"] = snapshot["command_center_recovery_result_timeline"]
    snapshot["risk_alerts"] = attach_recovery_priority_risk_alerts(
        attach_hard_risk_risk_alerts(
            snapshot.get("risk_alerts") or {},
            snapshot.get("hard_risk_packet") or {},
        ),
        snapshot.get("data_recovery_center") or {},
    )
    existing_market_profile = _as_mapping(snapshot.get("market_profile_evidence"))
    normalized_market_profile = market_profile_summary_service.build_market_profile_evidence_strip(
        market_type=existing_market_profile.get("market_type"),
        ticker=existing_market_profile.get("ticker"),
        name=existing_market_profile.get("name"),
        home_snapshot=snapshot,
    )
    if existing_market_profile:
        normalized_market_profile.update(existing_market_profile)
        normalized_market_profile["deepseek_called"] = False
    snapshot["market_profile_evidence"] = normalized_market_profile
    snapshot = attach_decision_loop_status(snapshot)
    return snapshot


def attach_decision_loop_status(
    snapshot: Any = None,
    *,
    data_capability_console: Any = None,
    provider_data_capability_cockpit: Any = None,
    old_workspace_packet_bridge: Any = None,
    analysis_method_packet: Any = None,
    projection_packet: Any = None,
    strategy_packet: Any = None,
    decision_packet: Any = None,
    deepseek_summary: Any = None,
) -> dict:
    payload = _as_mapping(snapshot)
    payload["decision_loop_status"] = loop_status_service.build_command_center_loop_status_view_model(
        data_capability_console=data_capability_console or payload.get("data_capability_console") or {},
        provider_data_capability_cockpit=provider_data_capability_cockpit or payload.get("provider_data_capability_cockpit") or {},
        old_workspace_packet_bridge=old_workspace_packet_bridge or payload.get("old_workspace_packet_bridge") or {},
        analysis_method_packet=analysis_method_packet or payload.get("analysis_method_packet") or {},
        market_profile_evidence=payload.get("market_profile_evidence") or {},
        projection_packet=projection_packet or payload.get("projection_packet") or {},
        strategy_packet=strategy_packet or payload.get("strategy_packet") or {},
        decision_packet=decision_packet or payload.get("decision_packet") or {},
        deepseek_summary=deepseek_summary or payload.get("deepseek_summary") or {},
        data_recovery_center=payload.get("data_recovery_center") or {},
    )
    return payload


def save_home_action_snapshot(snapshot: Mapping[str, Any], path: str | Path | None = None, base_dir: str | Path | None = None) -> Path:
    snapshot_path = Path(path) if path is not None else get_home_snapshot_path(base_dir)
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    payload = sanitize_snapshot_payload(snapshot)
    temp_path = snapshot_path.with_suffix(snapshot_path.suffix + ".tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    temp_path.replace(snapshot_path)
    return snapshot_path


def classify_data_freshness(timestamp: Any, today: Any = None) -> str:
    text = _to_text(timestamp)
    if not text or text == "暂无":
        return "missing"
    return "today" if text[:10] == _today_string(today) else "stale"


def build_data_freshness(timestamp: Any = None, errors: Any = None, deepseek_called: bool = False, today: Any = None) -> dict:
    error_list = _as_list(errors)
    if error_list:
        state, label = "partial_failed", "部分失败"
    else:
        state = classify_data_freshness(timestamp, today=today)
        label = {"today": "今日已刷新", "stale": "使用缓存", "missing": "待刷新"}[state]
    return {
        "state": state,
        "label": label,
        "last_updated": _to_text(timestamp, "暂无"),
        "deepseek_called": bool(deepseek_called),
    }


def _packet_data_coverage(live_packet: Any, decision_packet: Any, strategy_packet: Any) -> dict:
    decision = _as_mapping(decision_packet)
    coverage = _as_mapping(decision.get("data_coverage"))
    result = {}
    live = _as_mapping(live_packet)
    for key in MODULE_LABELS:
        state = _to_text(coverage.get(key))
        if not state:
            section = _as_mapping(live.get(key))
            if section.get("is_fresh") or _to_text(section.get("status")) in {"已刷新", "ready", "ok", "completed"}:
                state = "ready"
            elif section.get("last_success") or section.get("stale"):
                state = "cached"
            else:
                state = "missing"
        result[key] = state if state in {"ready", "cached", "missing"} else "missing"
    strategy_state = result.get("strategy_execution")
    if strategy_packet:
        status = _to_text(_as_mapping(strategy_packet).get("status"))
        strategy_state = "ready" if status in {"ready", "completed", "ok", "success"} else ("cached" if _as_mapping(strategy_packet).get("stale") else strategy_state)
    result["strategy_execution"] = strategy_state or "missing"
    result["decision"] = "ready" if decision else "missing"
    return result


def _extract_errors(*packets: Any) -> list[dict]:
    items = []
    for packet in packets:
        payload = _as_mapping(packet)
        raw_errors = payload.get("errors") or []
        if isinstance(raw_errors, (str, Mapping)):
            raw_errors = [raw_errors]
        if isinstance(raw_errors, (list, tuple)):
            for item in raw_errors:
                err = _as_mapping(item)
                if err:
                    message = _to_text(err.get("message") or err.get("error") or err.get("last_error"))
                    module = _to_text(err.get("module"), "模块")
                    updated_at = _to_text(err.get("updated_at") or payload.get("updated_at") or payload.get("finished_at"), "暂无")
                    source = _to_text(err.get("source"), "未加载")
                else:
                    message = _to_text(item)
                    module = "模块"
                    updated_at = _to_text(payload.get("updated_at") or payload.get("finished_at"), "暂无")
                    source = "未加载"
                if message:
                    items.append({"module": module, "message": message, "updated_at": updated_at, "source": source})
        for key in ("last_error", "error"):
            message = _to_text(payload.get(key))
            if message:
                items.append(
                    {
                        "module": _to_text(payload.get("module"), "模块"),
                        "message": message,
                        "updated_at": _to_text(payload.get("updated_at") or payload.get("finished_at"), "暂无"),
                        "source": _to_text(payload.get("source"), "未加载"),
                    }
                )
    deduped = []
    seen = set()
    for item in items:
        key = (item["module"], item["message"], item["updated_at"], item["source"])
        if key not in seen:
            seen.add(key)
            deduped.append(item)
    return deduped[:MAX_ERRORS]


def _normalize_capability_state(item: Mapping[str, Any]) -> str:
    state = _to_text(item.get("capability_state") or item.get("state"))
    if state:
        return state
    if item.get("permission_likely"):
        return "permission_denied"
    if item.get("ok"):
        return "available"
    return "unknown"


def build_data_capability_snapshot(data_capability_packet: Any = None) -> dict:
    packet = _as_mapping(data_capability_packet)
    raw_items = packet.get("items") or []
    if not isinstance(raw_items, (list, tuple)):
        raw_items = []
    items = []
    for raw in raw_items:
        payload = _as_mapping(raw)
        if not payload:
            continue
        state = _normalize_capability_state(payload)
        label = _to_text(payload.get("label") or payload.get("api") or payload.get("section"), "数据能力")
        items.append(
            {
                "key": _to_text(payload.get("section") or payload.get("api"), "data_capability"),
                "label": label,
                "provider": _to_text(payload.get("provider") or payload.get("source") or packet.get("source"), "数据能力"),
                "api": _to_text(payload.get("api")),
                "status": _to_text(payload.get("status") or payload.get("capability_label") or state, "待验证"),
                "state": state,
                "latest_date": _to_text(payload.get("latest_date")),
                "updated_at": _to_text(payload.get("updated_at")),
                "source": _to_text(payload.get("source") or packet.get("source"), "数据能力"),
                "action_hint": _to_text(payload.get("action_hint")),
                "error": _to_text(payload.get("error")),
            }
        )
    items = items[:MAX_CAPABILITY_ITEMS]
    available = [item["label"] for item in items if item["state"] == "available"]
    restricted = [item["label"] for item in items if item["state"] in CAPABILITY_RESTRICTED_STATES]
    pending = [item["label"] for item in items if item["state"] in CAPABILITY_PENDING_STATES]
    summary = (
        f"可用：{'、'.join(available) if available else '无'}｜"
        f"受限：{'、'.join(restricted) if restricted else '无'}｜"
        f"待验证：{'、'.join(pending) if pending else '无'}"
        if items
        else "尚未检测；页面打开不会自动请求 Tushare、AkShare、yfinance 或 Supabase。"
    )
    return {
        "source": _to_text(packet.get("source"), "数据能力"),
        "checked_at": _to_text(packet.get("checked_at") or packet.get("updated_at")),
        "summary": summary,
        "available_count": len(available),
        "restricted_count": len(restricted),
        "pending_count": len(pending),
        "items": items,
        "deepseek_called": False,
    }


def _interface_diagnostic_key(item: Mapping[str, Any]) -> tuple[str, str, str]:
    return (
        _to_text(item.get("provider")).lower(),
        _to_text(item.get("api")).lower(),
        _to_text(item.get("label")).lower(),
    )


def _interface_diagnostic_lookup(data_issue_explainer: Any = None) -> dict[tuple[str, str, str], dict]:
    payload = _as_mapping(data_issue_explainer)
    lookup = {}
    for raw in _as_list(payload.get("interface_diagnostic_items")):
        item = _as_mapping(raw)
        if not item:
            continue
        key = _interface_diagnostic_key(item)
        lookup[key] = item
        provider, api, label = key
        if api:
            lookup[(provider, api, "")] = item
        if label:
            lookup[(provider, "", label)] = item
    return lookup


def _find_interface_diagnostic(item: Mapping[str, Any], lookup: Mapping[tuple[str, str, str], dict]) -> dict:
    provider, api, label = _interface_diagnostic_key(item)
    candidates = [
        (provider, api, label),
        (provider, api, ""),
        (provider, "", label),
        ("", api, label),
        ("", api, ""),
        ("", "", label),
    ]
    for key in candidates:
        match = _as_mapping(lookup.get(key))
        if match:
            return match
    return {}


def _recovery_legacy_tab(writes_packet: Any = "", key: Any = "") -> str:
    text = _to_text(writes_packet) or _to_text(key)
    if text in {"hard_risk", "command_center_hard_risk_packet"}:
        return "天眼风控"
    if text in {"data_capability", "command_center_data_capability_packet", "akshare_manual_refresh"}:
        return "数据源体检"
    return _legacy_a_share_fact_legacy_tab(text, text)


def build_data_recovery_actions_snapshot(
    data_capability_console: Any = None,
    data_issue_explainer: Any = None,
    limit: int = MAX_CAPABILITY_ITEMS,
) -> list[dict]:
    console = _as_mapping(data_capability_console)
    diagnostic_lookup = _interface_diagnostic_lookup(data_issue_explainer)
    actions = []
    for raw in _as_list(console.get("recovery_actions")):
        item = _as_mapping(raw)
        if not item:
            continue
        label = _to_text(item.get("label"), "数据能力")
        diagnostic = _find_interface_diagnostic(item, diagnostic_lookup)
        writes_packet = _to_text(item.get("writes_packet"), "command_center_data_capability_packet")
        action_label = _to_text(item.get("action_label"), f"手动检查{label}")
        legacy_tab = _recovery_legacy_tab(writes_packet, item.get("key") or item.get("api"))
        api = _to_text(item.get("api"))
        diagnostic_answer = _to_text(
            diagnostic.get("diagnostic_answer") or item.get("diagnostic_answer") or item.get("meaning"),
            f"{label}仍需核对接口状态、日期和覆盖范围。",
        )
        actions.append(
            {
                "provider": _to_text(item.get("provider"), "数据源"),
                "label": label,
                "api": api,
                "state": _to_text(item.get("state"), "unknown"),
                "status_label": _to_text(item.get("status_label"), "待验证"),
                "priority": int(_to_number(item.get("priority")) or 3),
                "reason": _to_text(item.get("reason") or item.get("action_hint"), f"{label}仍待验证。"),
                "diagnostic_answer": diagnostic_answer,
                "interface_cause_key": _to_text(diagnostic.get("cause_key")),
                "interface_cause_label": _to_text(diagnostic.get("cause_label"), _to_text(item.get("status_label"), "待验证")),
                "interface_diagnostic_answer": diagnostic_answer,
                "action_label": action_label,
                "toolbox_entry": _to_text(item.get("toolbox_entry"), "高级工具箱 / 数据源体检"),
                "workspace_target": "高级工具箱（旧版保留）",
                "workspace_state_key": "workspace_mode_v2",
                "legacy_tab_state_key": "legacy_workspace_selected_tab",
                "legacy_tab": legacy_tab,
                "navigation_label": f"主导航切到高级工具箱（旧版保留）→ 高级工具模块选择{legacy_tab}；手动执行后回流 {writes_packet}。",
                "writes_packet": writes_packet,
                "refresh_policy": _to_text(item.get("refresh_policy"), "button_gated"),
                "recovery_button_context": (
                    f"点击“{action_label}”只检测 {api or label}，结果回流 {writes_packet}；DeepSeek 未调用。"
                ),
                "deepseek_called": False,
            }
        )
        if len(actions) >= max(1, int(limit or MAX_CAPABILITY_ITEMS)):
            break
    return actions


def _timeline_recovery_action_context(item: Mapping[str, Any]) -> str:
    label = _to_text(item.get("label"), "数据接口")
    api = _to_text(item.get("api")) or label
    writes_packet = _to_text(item.get("writes_packet"), "command_center_data_capability_packet")
    event_type = _to_text(item.get("event_type"))
    if event_type == "last_failure":
        return f"最近失败项，只检测 {api} 并回流 {writes_packet}；不会自动调用 DeepSeek 或重型任务。"
    if event_type == "manual_required":
        return f"需要手动按钮触发，只处理 {api} 并回流 {writes_packet}；页面打开不会自动请求外部接口。"
    if event_type == "cache_used":
        return f"当前依赖缓存，手动复核 {api} 后回流 {writes_packet}；缓存不能当作实时事实。"
    if event_type == "empty_recent":
        return f"近期无数据项，手动复核交易日、标的覆盖和 {api}；结果回流 {writes_packet}。"
    return f"手动核对 {api} 并回流 {writes_packet}；不会自动调用 DeepSeek、回测或全市场扫描。"


def build_data_health_timeline_recovery_actions(
    data_health_timeline: Any = None,
    limit: int = MAX_CAPABILITY_ITEMS,
) -> list[dict]:
    timeline = _as_mapping(data_health_timeline)
    actions = []
    seen = set()
    for raw in _as_list(timeline.get("items")):
        item = _as_mapping(raw)
        event_type = _to_text(item.get("event_type"))
        if event_type not in DATA_HEALTH_TIMELINE_RECOVERY_EVENTS:
            continue
        writes_packet = _to_text(item.get("writes_packet"), "command_center_data_capability_packet")
        label = _to_text(item.get("label"), "数据接口")
        api = _to_text(item.get("api"))
        dedupe_key = writes_packet or f"{_to_text(item.get('provider'))}:{api or label}"
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        legacy_tab = _recovery_legacy_tab(writes_packet, item.get("key") or api)
        action_label = _to_text(item.get("action_label"), f"手动检查{label}")
        message = _to_text(item.get("message"), f"{label}仍需核对接口状态、日期和覆盖范围。")
        status_label = _to_text(item.get("status_label"), "待验证")
        actions.append(
            {
                "key": f"data_health_timeline:{api or label}:{event_type}",
                "provider": _to_text(item.get("provider"), "数据源"),
                "api": api,
                "label": label,
                "source_type": "data_health_timeline",
                "source_label": "接口健康时间线",
                "event_type": event_type,
                "status": _to_text(item.get("state"), event_type),
                "status_label": status_label,
                "tone": _to_text(item.get("tone"), "missing"),
                "priority": DATA_HEALTH_TIMELINE_RECOVERY_PRIORITY.get(event_type, 4),
                "reason": message,
                "diagnostic_answer": message,
                "interface_diagnostic_answer": message,
                "decision_guardrail": _to_text(
                    item.get("decision_guardrail"),
                    f"{label}未恢复前不能作为加仓、追高或加融资依据。",
                ),
                "action_label": action_label,
                "toolbox_entry": _to_text(item.get("toolbox_entry"), "高级工具箱 / 数据源体检"),
                "workspace_target": "高级工具箱（旧版保留）",
                "workspace_state_key": "workspace_mode_v2",
                "legacy_tab_state_key": "legacy_workspace_selected_tab",
                "legacy_tab": legacy_tab,
                "navigation_label": f"主导航切到高级工具箱（旧版保留）→ 高级工具模块选择{legacy_tab}；手动执行后回流 {writes_packet}。",
                "writes_packet": writes_packet,
                "refresh_policy": _to_text(item.get("refresh_policy"), "button_gated"),
                "recovery_button_context": _timeline_recovery_action_context(item),
                "external_call_policy": "not_triggered",
                "deepseek_called": False,
            }
        )
    actions = sorted(actions, key=lambda action: (action["priority"], action["label"], action["writes_packet"]))
    return actions[: max(1, int(limit or MAX_CAPABILITY_ITEMS))]


def _a_share_fact_recovery_state(packet: Mapping[str, Any], writes_packet: str = "") -> str:
    explicit = _to_text(packet.get("recovery_state")).lower()
    if explicit in {"recovered", "blocked", "waiting"}:
        return explicit
    return _tool_packet_recovery_state(packet, writes_packet)


def _a_share_fact_next_action(label: str, recovery_state: str, writes_packet: str, action_label: str) -> str:
    if recovery_state == "recovered":
        return f"{label}已写回 {writes_packet}；执行前复核交易日、来源和风险纪律。"
    if recovery_state == "blocked":
        return f"{label}仍受限；点击“{action_label}”后只检测这一项，结果回流 {writes_packet}。"
    return f"{label}待验证；需要时点击“{action_label}”，页面打开不会自动请求 Tushare。"


def _a_share_fact_diagnostic_text(label: str, recovery_state: str, status_label: str) -> str:
    if recovery_state == "recovered":
        return f"{label}已有可读 packet，可进入综合中心证据链。"
    if recovery_state == "blocked":
        return f"{label}当前为{status_label}，不能把缺失数据当成利好或无风险。"
    return f"{label}尚未形成当日可验证事实；保持空态或缓存，等待手动检测。"


def _a_share_fact_summary_item(config: Mapping[str, Any], packet: Any = None) -> dict:
    payload = _as_mapping(packet)
    writes_packet = _to_text(config.get("writes_packet"), "command_center_packet")
    recovery_state = _a_share_fact_recovery_state(payload, writes_packet)
    status = _to_text(payload.get("status"), "waiting")
    data_status = _to_text(payload.get("data_status") or payload.get("cache_state"), "missing")
    capability_state = _to_text(payload.get("capability_state") or payload.get("state"), "requires_manual_refresh")
    status_label = _to_text(payload.get("status_label") or payload.get("capability_label") or status, "待验证")
    updated_at = _to_text(
        payload.get("updated_at")
        or payload.get("checked_at")
        or payload.get("generated_at")
        or payload.get("trade_date")
        or payload.get("latest_date"),
        "暂无",
    )
    source = _to_text(payload.get("source") or payload.get("source_key"), _to_text(config.get("source_fallback"), "本地 packet"))
    if recovery_state == "recovered":
        tone = "ready"
        readable_state = "已回流"
    elif recovery_state == "blocked":
        tone = "failed"
        readable_state = "仍受限"
    else:
        tone = "missing"
        readable_state = "待验证"
    manual_config = TOOL_RECOVERY_MANUAL_CHECKS.get(writes_packet, {})
    action_label = _to_text(manual_config.get("button_label"), f"手动检测{_to_text(config.get('label'), 'A股事实')}")
    label = _to_text(config.get("label"), "A股事实")
    legacy_tab = _legacy_a_share_fact_legacy_tab(config.get("key"), writes_packet)
    return {
        "key": _to_text(config.get("key")),
        "label": label,
        "packet_key": _to_text(config.get("packet_key")),
        "writes_packet": writes_packet,
        "recovery_state": recovery_state,
        "readable_state": readable_state,
        "tone": tone,
        "status": status,
        "data_status": data_status,
        "capability_state": capability_state,
        "status_label": status_label,
        "updated_at": updated_at,
        "source": source,
        "action_label": action_label if recovery_state != "recovered" else "查看回流结果",
        "next_action": _a_share_fact_next_action(label, recovery_state, writes_packet, action_label),
        "diagnostic_answer": _a_share_fact_diagnostic_text(label, recovery_state, status_label),
        "packet_status_text": f"{readable_state}｜{status_label}｜{writes_packet}",
        "toolbox_entry": f"高级工具箱 / {legacy_tab}",
        "workspace_target": "高级工具箱（旧版保留）",
        "workspace_state_key": "workspace_mode_v2",
        "legacy_tab": legacy_tab,
        "legacy_tab_state_key": "legacy_workspace_selected_tab",
        "navigation_label": f"主导航切到高级工具箱（旧版保留）→ 高级工具模块选择{legacy_tab}；手动执行后回流 {writes_packet}。",
        "refresh_policy": "not_needed" if recovery_state == "recovered" else "button_gated",
        "source_label": "A股事实回流",
        "deepseek_called": False,
    }


def build_a_share_fact_recovery_summary(snapshot: Any = None) -> dict:
    payload = _as_mapping(snapshot)
    items = [
        _a_share_fact_summary_item(config, payload.get(config["packet_key"]) or payload.get(config["writes_packet"]))
        for config in A_SHARE_FACT_RECOVERY_SOURCES
    ]
    recovered = [item for item in items if item["recovery_state"] == "recovered"]
    blocked = [item for item in items if item["recovery_state"] == "blocked"]
    waiting = [item for item in items if item["recovery_state"] == "waiting"]
    total = len(items)
    if len(recovered) == total:
        tone = "ready"
        next_action = "五类 A股事实已回流；执行前仍需复核交易日、来源和风险纪律。"
    elif blocked:
        tone = "failed"
        first = blocked[0]
        next_action = f"优先处理 {first['label']}：检查权限、积分、交易日或进入数据恢复中心手动恢复。"
    elif recovered:
        tone = "stale"
        next_action = "继续手动补齐待验证事实；不要把缺失数据当成无风险。"
    else:
        tone = "missing"
        next_action = "点击刷新今日基础数据或进入数据恢复中心；页面打开不会自动请求 Tushare。"
    summary = f"A股事实 {total} 项：已回流 {len(recovered)}｜仍受限 {len(blocked)}｜待验证 {len(waiting)}"
    return {
        "title": "A股事实回流",
        "summary": summary,
        "tone": tone,
        "recovered_count": len(recovered),
        "blocked_count": len(blocked),
        "waiting_count": len(waiting),
        "total_count": total,
        "items": items,
        "next_action": next_action,
        "safe_mode_text": "这里只汇总本地 packet 状态；不会自动调用 Tushare、DeepSeek、回测或全市场扫描。",
        "deepseek_called": False,
    }


def _a_share_evidence_ledger_decision_impact(item: Mapping[str, Any]) -> str:
    label = _to_text(item.get("label"), "A股证据")
    state = _to_text(item.get("recovery_state"), "waiting")
    if state == "recovered":
        return f"{label}已回流，可进入证据链辅助判断；执行前仍需复核交易日、来源和仓位纪律。"
    if state == "blocked":
        return f"{label}仍受限，阻断加仓/追高/加融资依据；不能把缺失数据当成利好或无风险。"
    return f"{label}待验证，只能展示安全空态或缓存；不能作为买入、追高或放大仓位依据。"


def build_a_share_evidence_recovery_ledger(snapshot: Any = None) -> dict:
    payload = _as_mapping(snapshot)
    fact_summary = _as_mapping(payload.get("a_share_fact_recovery_summary"))
    if not fact_summary:
        fact_summary = build_a_share_fact_recovery_summary(payload)
    items = []
    for raw in _as_list(fact_summary.get("items")):
        item = _as_mapping(raw)
        if not item:
            continue
        state = _to_text(item.get("recovery_state"), "waiting")
        items.append(
            {
                "key": _to_text(item.get("key"), "a_share_evidence"),
                "label": _to_text(item.get("label"), "A股证据"),
                "ledger_state": state,
                "ledger_label": _to_text(item.get("readable_state"), "待验证"),
                "tone": _to_text(item.get("tone"), "missing"),
                "status_label": _to_text(item.get("status_label"), "待验证"),
                "updated_at": _to_text(item.get("updated_at"), "暂无"),
                "source": _to_text(item.get("source"), "本地 packet"),
                "writes_packet": _to_text(item.get("writes_packet"), "command_center_packet"),
                "toolbox_entry": _to_text(item.get("toolbox_entry"), "高级工具箱"),
                "action_label": _to_text(item.get("action_label"), "手动检测"),
                "next_action": _to_text(item.get("next_action"), "按数据恢复中心手动处理。"),
                "decision_impact": _a_share_evidence_ledger_decision_impact(item),
                "navigation_label": _to_text(item.get("navigation_label"), "进入高级工具箱对应模块后手动检测。"),
                "refresh_policy": _to_text(item.get("refresh_policy"), "button_gated"),
                "deepseek_called": False,
                "external_call_policy": "not_triggered",
            }
        )
    recovered_count = len([item for item in items if item["ledger_state"] == "recovered"])
    blocked_count = len([item for item in items if item["ledger_state"] == "blocked"])
    waiting_count = len([item for item in items if item["ledger_state"] not in {"recovered", "blocked"}])
    if blocked_count:
        status = "blocked"
        tone = "failed"
        headline = f"A股证据回流仍有 {blocked_count} 项阻断"
        next_action = "先处理仍受限证据；未恢复前不能把缺口写成安全或利好。"
    elif waiting_count:
        status = "partial"
        tone = "stale" if recovered_count else "missing"
        headline = f"A股证据已回流 {recovered_count}｜待验证 {waiting_count}"
        next_action = "继续按恢复入口补齐待验证证据；页面打开不会自动请求 Tushare。"
    else:
        status = "ready"
        tone = "ready"
        headline = "五类 A股证据已形成回流总账"
        next_action = "可进入证据链复核；执行前仍需价格、纪律和仓位确认。"
    return {
        "title": "A股证据回流总账",
        "status": status,
        "tone": tone,
        "headline": headline,
        "summary": f"已回流 {recovered_count}｜仍受限 {blocked_count}｜待验证 {waiting_count}",
        "items": items,
        "recovered_count": recovered_count,
        "blocked_count": blocked_count,
        "waiting_count": waiting_count,
        "total_count": len(items),
        "next_action": next_action,
        "safe_mode_text": "这里只读取本地 packet 和恢复结果；不会自动调用 Tushare、DeepSeek、回测或全市场扫描。",
        "deepseek_called": False,
        "external_call_policy": "not_triggered",
    }


STRATEGY_PREREQUISITE_RECOVERY_SOURCES = (
    {
        "packet_key": "quant_packet",
        "key": "quant_projection",
        "label": "量化推演",
        "writes_packet": "command_center_quant_packet",
        "toolbox_entry": "高级工具箱 / 量化推演",
        "action_label": "手动生成量化推演",
        "recovered_impact": "量化推演已回流，可辅助评分、趋势和执行节奏；仍不能替代仓位纪律。",
        "cached_impact": "量化推演使用缓存，只能作为参考；执行前需确认交易日和行情状态。",
        "blocked_impact": "量化推演仍失败或受限，策略执行只能保持低置信度/待验证，不能把评分当成事实。",
        "waiting_impact": "量化推演待手动生成，策略执行不能假装已有评分或单票量化诊断。",
        "next_action": "进入高级工具箱 / 量化推演手动生成，成功后回流 command_center_quant_packet。",
    },
    {
        "packet_key": "discipline_packet",
        "key": "discipline_backtest",
        "label": "交易纪律/回测",
        "writes_packet": "command_center_discipline_packet",
        "toolbox_entry": "高级工具箱 / 交易纪律实验室",
        "action_label": "手动运行回测或读取纪律缓存",
        "recovered_impact": "纪律/回测证据已回流，可约束加仓、减仓和失效条件；不直接决定买卖。",
        "cached_impact": "纪律/回测使用缓存，可作为风险约束；执行前需确认回测窗口和数据来源。",
        "blocked_impact": "纪律/回测仍失败或受限，不能把策略建议当成已验证执行方案。",
        "waiting_impact": "纪律/回测待手动运行，策略执行只能展示待验证条件，不能自动跑回测。",
        "next_action": "进入高级工具箱 / 交易纪律实验室手动运行回测，成功后回流 command_center_discipline_packet。",
    },
)


def _strategy_prerequisite_decision_impact(config: Mapping[str, Any], display_state: Mapping[str, Any]) -> str:
    status = _to_text(display_state.get("status"), "waiting")
    if status == "recovered":
        return _to_text(config.get("recovered_impact"))
    if status == "cached":
        return _to_text(config.get("cached_impact"))
    if status == "blocked":
        return _to_text(config.get("blocked_impact"))
    return _to_text(config.get("waiting_impact"))


def build_strategy_prerequisite_recovery_ledger(snapshot: Any = None) -> dict:
    payload = _as_mapping(snapshot)
    items = []
    for config in STRATEGY_PREREQUISITE_RECOVERY_SOURCES:
        packet_key = _to_text(config.get("packet_key"))
        writes_packet = _to_text(config.get("writes_packet"))
        packet = _as_mapping(payload.get(packet_key) or payload.get(writes_packet))
        display_state = _recovery_display_state(packet, writes_packet)
        items.append(
            {
                "key": _to_text(config.get("key"), packet_key),
                "label": _to_text(config.get("label"), "策略前置能力"),
                "ledger_state": _to_text(display_state.get("status"), "waiting"),
                "ledger_label": _to_text(display_state.get("label"), "待验证"),
                "tone": _to_text(display_state.get("tone"), "missing"),
                "status_label": _to_text(
                    packet.get("status_label")
                    or packet.get("backtest_status")
                    or packet.get("data_status")
                    or packet.get("status"),
                    "待验证",
                ),
                "updated_at": _to_text(packet.get("updated_at") or packet.get("generated_at"), "暂无"),
                "source": _to_text(packet.get("source"), "本地 packet"),
                "writes_packet": writes_packet,
                "toolbox_entry": _to_text(config.get("toolbox_entry"), "高级工具箱"),
                "action_label": _to_text(config.get("action_label"), "手动恢复"),
                "next_action": _to_text(config.get("next_action"), "进入高级工具箱手动恢复并回流 packet。"),
                "decision_impact": _strategy_prerequisite_decision_impact(config, display_state),
                "refresh_policy": "button_gated",
                "deepseek_called": False,
                "external_call_policy": "not_triggered",
            }
        )
    recovered_count = len([item for item in items if item["ledger_state"] == "recovered"])
    cached_count = len([item for item in items if item["ledger_state"] == "cached"])
    blocked_count = len([item for item in items if item["ledger_state"] == "blocked"])
    waiting_count = len([item for item in items if item["ledger_state"] not in {"recovered", "cached", "blocked"}])
    if blocked_count:
        status = "blocked"
        tone = "failed"
        headline = f"策略前置能力仍有 {blocked_count} 项阻断"
        next_action = "先处理失败或受限的前置能力；未恢复前不能把策略建议当成已验证执行方案。"
    elif waiting_count:
        status = "partial"
        tone = "stale" if recovered_count or cached_count else "missing"
        headline = f"策略前置能力待手动补齐 {waiting_count} 项"
        next_action = "进入高级工具箱手动补齐量化或纪律能力；页面打开不会自动运行回测或扫描。"
    elif cached_count:
        status = "cached"
        tone = "stale"
        headline = "策略前置能力使用缓存"
        next_action = "缓存可辅助判断；执行前复核交易日、数据来源和纪律边界。"
    else:
        status = "ready"
        tone = "ready"
        headline = "策略前置能力已回流"
        next_action = "量化和纪律可进入策略执行闭环；仍需遵守仓位和风险预算。"
    return {
        "title": "策略前置能力回流总账",
        "status": status,
        "tone": tone,
        "headline": headline,
        "summary": f"已回流 {recovered_count}｜使用缓存 {cached_count}｜仍受限 {blocked_count}｜待手动 {waiting_count}",
        "items": items,
        "recovered_count": recovered_count,
        "cached_count": cached_count,
        "blocked_count": blocked_count,
        "waiting_count": waiting_count,
        "total_count": len(items),
        "next_action": next_action,
        "safe_mode_text": "这里只读取本地 packet 和缓存；不会自动运行回测、DeepSeek、全市场扫描或重型数据接口。",
        "deepseek_called": False,
        "external_call_policy": "not_triggered",
    }


OLD_WORKSPACE_DATA_ABSENCE_CAUSES = {
    "permission_or_points": {
        "label": "权限/积分不足",
        "tone": "failed",
        "diagnostic_answer": (
            "Tushare token 或基础行情可用，不代表每个旧工作台专业接口都已开通；"
            "龙虎榜、融资融券、涨跌停情绪、筹码等接口可能仍需要单独权限或积分。"
        ),
        "next_action": "先确认具体接口权限/积分，再手动检测；不能把权限缺口当成行情不存在。",
        "decision_guardrail": "未恢复前阻断加仓、追高、加融资和把风险写成已排除。",
    },
    "session_skip": {
        "label": "本会话跳过",
        "tone": "failed",
        "diagnostic_answer": "某接口本会话已经被判定受限或失败，系统会跳过重复请求来防止页面卡顿。",
        "next_action": "确认权限或网络恢复后，手动点击对应检测按钮重试。",
        "decision_guardrail": "本会话跳过不是无风险；只能保持安全空态或缓存观察。",
    },
    "no_recent_record": {
        "label": "近期无记录",
        "tone": "missing",
        "diagnostic_answer": "接口可读也可能搜不到：非交易日、数据尚未发布、标的未上榜、窗口期太短或接口不覆盖都会导致空结果。",
        "next_action": "核对交易日、发布时间、标的覆盖和查询窗口，必要时手动刷新。",
        "decision_guardrail": "近期无记录不能写成利好、无风险或可以加仓。",
    },
    "cache_or_fallback": {
        "label": "缓存/替代口径",
        "tone": "stale",
        "diagnostic_answer": "缓存能防白屏，替代口径能保留观察，但它们都不是实时已验证事实。",
        "next_action": "执行前复核缓存日期、来源和口径；需要实时证据时再手动刷新。",
        "decision_guardrail": "缓存只辅助看盘，不能单独支撑交易动作。",
    },
    "manual_gate": {
        "label": "必须手动触发",
        "tone": "missing",
        "diagnostic_answer": "重型刷新、批量扫描、回测和外部接口不会在页面打开时自动执行。",
        "next_action": "需要时点击对应按钮，等待结果回流到综合中心 packet。",
        "decision_guardrail": "未手动生成前，只能显示待验证状态。",
    },
    "config_or_network": {
        "label": "配置/网络失败",
        "tone": "failed",
        "diagnostic_answer": "本地配置、网络或接口调用失败会让旧工作台能力不可用。",
        "next_action": "检查 token、网络、依赖和接口状态；失败时保留缓存或安全空态。",
        "decision_guardrail": "配置/网络失败时不能把缺失数据当作行情判断。",
    },
    "unverified": {
        "label": "状态待验证",
        "tone": "missing",
        "diagnostic_answer": "当前只有不完整的本地状态，尚不能证明接口可用或不可用。",
        "next_action": "按数据恢复中心手动检测并回流 packet。",
        "decision_guardrail": "待验证数据不能作为加仓、追高或加融资依据。",
    },
}


def _old_workspace_absence_cause_key(item: Mapping[str, Any]) -> str:
    explicit = _to_text(item.get("cause_key") or item.get("interface_cause_key")).lower()
    if explicit in OLD_WORKSPACE_DATA_ABSENCE_CAUSES:
        return explicit
    state_text = " ".join(
        _to_text(item.get(key))
        for key in (
            "state",
            "status",
            "status_label",
            "data_status",
            "capability_state",
            "recovery_state",
            "reason",
            "diagnostic_answer",
            "interface_diagnostic_answer",
            "meaning",
            "message",
        )
    ).lower()
    if any(token in state_text for token in ("permission", "permission_denied", "权限", "积分")):
        return "permission_or_points"
    if any(token in state_text for token in ("disabled_this_session", "本会话跳过", "跳过重复")):
        return "session_skip"
    if any(token in state_text for token in ("empty_recent", "近期无", "暂无数据", "无记录", "未上榜", "非交易日")):
        return "no_recent_record"
    if any(token in state_text for token in ("stale_cache", "fallback_used", "using_cache", "cached", "缓存", "替代口径")):
        return "cache_or_fallback"
    if any(token in state_text for token in ("requires_manual_refresh", "manual_required", "button_gated", "手动", "重型")):
        return "manual_gate"
    if any(token in state_text for token in ("not_configured", "network_failed", "network", "配置", "网络", "failed", "error", "失败")):
        return "config_or_network"
    return "unverified"


def _infer_old_workspace_writes_packet(item: Mapping[str, Any]) -> str:
    explicit = _to_text(item.get("writes_packet"))
    if explicit:
        return explicit
    api = _to_text(item.get("api") or item.get("table")).lower()
    if api in OLD_WORKSPACE_API_TO_WRITES_PACKET:
        return OLD_WORKSPACE_API_TO_WRITES_PACKET[api]
    key = _to_text(item.get("key") or item.get("section")).lower()
    for config in A_SHARE_FACT_RECOVERY_SOURCES:
        if key == _to_text(config.get("key")).lower():
            return _to_text(config.get("writes_packet"), "command_center_packet")
    return "command_center_data_capability_packet"


def _old_workspace_absence_item(raw: Any = None, source_type: str = "") -> dict:
    item = _as_mapping(raw)
    if not item:
        return {}
    cause_key = _old_workspace_absence_cause_key(item)
    cause = OLD_WORKSPACE_DATA_ABSENCE_CAUSES[cause_key]
    label = _to_text(item.get("label") or item.get("module") or item.get("api") or item.get("key"), "旧工作台能力")
    api = _to_text(item.get("api") or item.get("table"))
    provider = _to_text(item.get("provider") or item.get("source"), "本地 packet")
    writes_packet = _infer_old_workspace_writes_packet(item)
    legacy_tab = _to_text(item.get("legacy_tab"), _recovery_legacy_tab(writes_packet, item.get("key") or api or label))
    toolbox_entry = _to_text(item.get("toolbox_entry"), f"高级工具箱 / {legacy_tab}")
    action_label = _to_text(item.get("action_label") or item.get("manual_check_button_label"), f"手动检测{label}")
    return {
        "key": _to_text(item.get("key") or api or label, "old_workspace_data"),
        "label": label,
        "provider": provider,
        "api": api,
        "cause_key": cause_key,
        "cause_label": _to_text(item.get("cause_label") or item.get("interface_cause_label"), cause["label"]),
        "tone": _to_text(item.get("tone"), cause["tone"]),
        "status_label": _to_text(item.get("status_label") or item.get("status") or item.get("readable_state"), cause["label"]),
        "diagnostic_answer": _to_text(
            item.get("interface_diagnostic_answer")
            or item.get("diagnostic_answer")
            or item.get("why_not_found")
            or item.get("meaning"),
            cause["diagnostic_answer"],
        ),
        "next_action": _to_text(item.get("next_action") or item.get("action_hint"), cause["next_action"]),
        "decision_guardrail": _to_text(item.get("decision_guardrail"), cause["decision_guardrail"]),
        "action_label": action_label,
        "writes_packet": writes_packet,
        "toolbox_entry": toolbox_entry,
        "workspace_target": "高级工具箱（旧版保留）",
        "workspace_state_key": "workspace_mode_v2",
        "legacy_tab": legacy_tab,
        "legacy_tab_state_key": "legacy_workspace_selected_tab",
        "navigation_label": f"主导航切到高级工具箱（旧版保留）→ 高级工具模块选择{legacy_tab}；手动执行后回流 {writes_packet}。",
        "source_type": _to_text(source_type, "local_status"),
        "updated_at": _to_text(item.get("updated_at") or item.get("latest_date"), "暂无"),
        "refresh_policy": _to_text(item.get("refresh_policy"), "button_gated"),
        "recovery_button_context": _to_text(
            item.get("recovery_button_context") or item.get("button_context"),
            f"点击“{action_label}”只处理 {api or label} 并回流 {writes_packet}；不会自动调用 DeepSeek、回测、全市场扫描或重型接口。",
        ),
        "deepseek_called": False,
        "external_call_policy": "not_triggered",
    }


def _collect_old_workspace_absence_items(snapshot: Mapping[str, Any]) -> list[dict]:
    candidates: list[dict] = []
    data_issue_explainer = _as_mapping(snapshot.get("data_issue_explainer"))
    for raw in _as_list(data_issue_explainer.get("interface_diagnostic_items")):
        candidates.append(_old_workspace_absence_item(raw, source_type="data_issue_explainer"))
    data_recovery_center = _as_mapping(snapshot.get("data_recovery_center"))
    for raw in _as_list(data_recovery_center.get("actions")):
        candidates.append(_old_workspace_absence_item(raw, source_type="data_recovery_center"))
    for raw in _as_list(_as_mapping(snapshot.get("legacy_a_share_gap_summary")).get("items")):
        candidates.append(_old_workspace_absence_item(raw, source_type="legacy_a_share_gap"))
    for raw in _as_list(_as_mapping(snapshot.get("a_share_fact_recovery_summary")).get("items")):
        candidates.append(_old_workspace_absence_item(raw, source_type="a_share_fact_recovery"))
    deduped = []
    seen = set()
    for item in candidates:
        if not item:
            continue
        key = (
            _to_text(item.get("cause_key")),
            _to_text(item.get("provider")).lower(),
            _to_text(item.get("api")).lower(),
            _to_text(item.get("label")).lower(),
            _to_text(item.get("writes_packet")),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped[:MAX_CAPABILITY_ITEMS]


def build_old_workspace_data_absence_ledger(snapshot: Any = None) -> dict:
    payload = _as_mapping(snapshot)
    items = _collect_old_workspace_absence_items(payload)
    cause_items = []
    for cause_key, config in OLD_WORKSPACE_DATA_ABSENCE_CAUSES.items():
        examples = [item for item in items if item["cause_key"] == cause_key]
        if not examples and cause_key != "unverified":
            continue
        if not examples and items:
            continue
        cause_items.append(
            {
                "key": cause_key,
                "label": config["label"],
                "tone": config["tone"],
                "count": len(examples),
                "examples": examples[:4],
                "example_labels": "、".join(_to_text(item.get("label"), "旧能力") for item in examples[:4]) or "暂无",
                "diagnostic_answer": config["diagnostic_answer"],
                "next_action": config["next_action"],
                "decision_guardrail": config["decision_guardrail"],
                "deepseek_called": False,
                "external_call_policy": "not_triggered",
            }
        )
        if not items:
            break
    counts = {key: len([item for item in items if item["cause_key"] == key]) for key in OLD_WORKSPACE_DATA_ABSENCE_CAUSES}
    p0_count = counts["permission_or_points"] + counts["session_skip"] + counts["config_or_network"]
    p1_count = counts["no_recent_record"] + counts["cache_or_fallback"] + counts["manual_gate"]
    if p0_count:
        status = "blocked"
        tone = "failed"
        headline = "旧工作台数据缺失存在 P0 阻断原因"
        next_action = "优先处理权限/积分、本会话跳过、配置或网络失败；不要把缺口当成行情不存在。"
    elif p1_count:
        status = "partial"
        tone = "stale"
        headline = "旧工作台数据以缓存、近期无记录或手动门控为主"
        next_action = "执行前复核交易日、缓存时间和接口覆盖范围；必要时手动刷新。"
    elif items:
        status = "ready"
        tone = "ready"
        headline = "旧工作台数据缺失原因已整理"
        next_action = "继续按数据恢复中心维护 packet 回流。"
    else:
        status = "missing"
        tone = "missing"
        headline = "旧工作台数据缺失原因待检测"
        next_action = "先点击刷新或对应手动检测按钮；页面打开不会自动 ping 外部接口。"
    summary = (
        f"权限/积分 {counts['permission_or_points']}｜本会话跳过 {counts['session_skip']}｜"
        f"近期无记录 {counts['no_recent_record']}｜缓存/替代 {counts['cache_or_fallback']}｜"
        f"需手动 {counts['manual_gate']}"
    )
    return {
        "title": "旧工作台数据缺失原因总账",
        "status": status,
        "tone": tone,
        "headline": headline,
        "summary": summary,
        "items": items,
        "cause_items": cause_items,
        "permission_count": counts["permission_or_points"],
        "session_skip_count": counts["session_skip"],
        "no_recent_record_count": counts["no_recent_record"],
        "cache_or_fallback_count": counts["cache_or_fallback"],
        "manual_gate_count": counts["manual_gate"],
        "config_or_network_count": counts["config_or_network"],
        "total_count": len(items),
        "short_answer": (
            "Tushare 拉满基础连接，不等于每个旧工作台专业接口都有当日可用证据；"
            "现在按原因分账，避免把权限、缓存或无记录误读成交易信号。"
        ),
        "next_action": next_action,
        "safe_mode_text": "这里只读取本地数据能力、恢复队列和旧工具 packet；不会自动调用 Tushare、AkShare、yfinance、Supabase、DeepSeek、回测或全市场扫描。",
        "deepseek_called": False,
        "external_call_policy": "not_triggered",
    }


def _provider_cockpit_name(provider: Any = "") -> str:
    text = _to_text(provider, "数据源")
    if "Tushare" in text:
        return "Tushare"
    if "AkShare" in text:
        return "AkShare"
    if "yfinance" in text or "Yahoo" in text:
        return "yfinance"
    if "Supabase" in text:
        return "Supabase"
    return text


def _provider_cockpit_row(raw: Any = None) -> dict:
    item = _as_mapping(raw)
    if not item:
        return {}
    provider = _provider_cockpit_name(item.get("provider") or item.get("source"))
    state = _to_text(item.get("state") or item.get("capability_state") or item.get("status"), "unknown")
    category = _to_text(item.get("category"))
    if not category:
        if state in {"available", "ready", "ok", "success", "可用"}:
            category = "available"
        elif state in CAPABILITY_RESTRICTED_STATES or state in {"permission_denied", "disabled_this_session", "not_configured", "network_failed", "failed", "error", "权限不足", "本会话跳过", "未配置", "网络失败"}:
            category = "blocked"
        elif state == "requires_manual_refresh" or _to_text(item.get("refresh_policy")) in {"button_gated", "manual_required"}:
            category = "manual"
        else:
            category = "stale"
    return {
        "provider": provider,
        "label": _to_text(item.get("label") or item.get("module") or item.get("api"), "数据能力"),
        "api": _to_text(item.get("api") or item.get("table")),
        "state": state,
        "category": category,
        "status_label": _to_text(item.get("status_label") or item.get("status") or item.get("capability_label"), state),
        "tone": _to_text(item.get("tone"), "ready" if category == "available" else "failed" if category == "blocked" else "missing" if category == "manual" else "stale"),
        "latest_date": _to_text(item.get("latest_date") or item.get("date") or item.get("trade_date")),
        "last_checked": _to_text(item.get("last_checked") or item.get("checked_at") or item.get("updated_at")),
        "last_success": _to_text(item.get("last_success") or item.get("last_success_text") or item.get("latest_date")),
        "meaning": _to_text(item.get("meaning") or item.get("diagnostic_answer") or item.get("reason"), "仍需核对接口状态、日期和覆盖范围。"),
        "decision_guardrail": _to_text(item.get("decision_guardrail") or item.get("decision_impact"), "缺失或未验证不能作为加仓、追高或加融资依据。"),
        "writes_packet": _to_text(item.get("writes_packet") or _infer_old_workspace_writes_packet(item), "command_center_data_capability_packet"),
        "refresh_policy": _to_text(item.get("refresh_policy"), "button_gated"),
        "deepseek_called": False,
        "external_call_policy": "not_triggered",
    }


def _collect_provider_cockpit_rows(snapshot: Mapping[str, Any]) -> list[dict]:
    candidates: list[dict] = []
    data_health_ledger = _as_mapping(snapshot.get("data_health_ledger"))
    candidates.extend(_provider_cockpit_row(item) for item in _as_list(data_health_ledger.get("rows")))
    data_capability = _as_mapping(snapshot.get("data_capability"))
    candidates.extend(_provider_cockpit_row(item) for item in _as_list(data_capability.get("items")))
    data_issue_explainer = _as_mapping(snapshot.get("data_issue_explainer"))
    candidates.extend(_provider_cockpit_row(item) for item in _as_list(data_issue_explainer.get("interface_diagnostic_items")))
    deduped = []
    seen = set()
    for item in candidates:
        if not item:
            continue
        key = (
            _to_text(item.get("provider")).lower(),
            _to_text(item.get("api")).lower(),
            _to_text(item.get("label")).lower(),
            _to_text(item.get("state")).lower(),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _provider_cockpit_status(rows: list[dict]) -> tuple[str, str, str]:
    if not rows:
        return "missing", "missing", "待检测"
    if any(row["category"] == "blocked" for row in rows):
        return "blocked", "failed", "受限"
    if any(row["category"] in {"manual", "stale"} for row in rows):
        return "partial", "stale", "待复核"
    return "ready", "ready", "可用"


def build_provider_data_capability_cockpit(snapshot: Any = None) -> dict:
    payload = _as_mapping(snapshot)
    rows = _collect_provider_cockpit_rows(payload)
    provider_cards = []
    provider_rows_by_name: dict[str, list[dict]] = {}
    for row in rows:
        provider_rows_by_name.setdefault(_provider_cockpit_name(row.get("provider")), []).append(row)
    for provider, config in PROVIDER_CAPABILITY_COCKPIT_CONFIG.items():
        provider_rows = provider_rows_by_name.get(provider, [])
        available = [row for row in provider_rows if row["category"] == "available"]
        blocked = [row for row in provider_rows if row["category"] == "blocked"]
        manual = [row for row in provider_rows if row["category"] == "manual"]
        stale = [row for row in provider_rows if row["category"] == "stale"]
        status, tone, status_label = _provider_cockpit_status(provider_rows)
        first_attention = (blocked or manual or stale or available or [{}])[0]
        last_success = _to_text(
            first_attention.get("last_success") or first_attention.get("latest_date"),
            "暂无" if not available else "已返回可用结果",
        )
        last_failure = "、".join(_to_text(row.get("label"), "数据能力") for row in blocked[:3]) or "无"
        action_label = _to_text(config.get("action_label"), f"手动检测{provider}")
        legacy_tab = _to_text(config.get("legacy_tab"), "数据源体检")
        recovery_action = {
            "key": f"provider_cockpit:{provider}",
            "label": _to_text(config.get("label"), provider),
            "provider": provider,
            "api": _to_text(first_attention.get("api")),
            "state": status,
            "status_label": status_label,
            "tone": tone,
            "action_label": action_label,
            "toolbox_entry": f"高级工具箱 / {legacy_tab}",
            "workspace_target": "高级工具箱（旧版保留）",
            "workspace_state_key": "workspace_mode_v2",
            "legacy_tab_state_key": "legacy_workspace_selected_tab",
            "legacy_tab": legacy_tab,
            "navigation_label": f"主导航切到高级工具箱（旧版保留）→ 高级工具模块选择{legacy_tab}；手动处理 {provider} 数据能力。",
            "writes_packet": _to_text(first_attention.get("writes_packet"), "command_center_data_capability_packet"),
            "refresh_policy": "button_gated",
            "recovery_button_context": f"只打开 {provider} 相关高级工具入口；不会自动调用外部接口、DeepSeek、回测或全市场扫描。",
            "deepseek_called": False,
            "external_call_policy": "not_triggered",
        }
        provider_cards.append(
            {
                "provider": provider,
                "label": _to_text(config.get("label"), provider),
                "role": _to_text(config.get("role"), "数据源"),
                "status": status,
                "tone": tone,
                "status_label": status_label,
                "summary": f"可用 {len(available)}｜受限 {len(blocked)}｜需手动 {len(manual)}｜缓存/待验证 {len(stale)}",
                "available_count": len(available),
                "blocked_count": len(blocked),
                "manual_count": len(manual),
                "stale_count": len(stale),
                "total_count": len(provider_rows),
                "last_success": last_success,
                "last_failure": last_failure,
                "next_action": _to_text(config.get("next_action"), "按数据恢复中心手动处理。"),
                "decision_guardrail": (
                    f"{provider} 受限项恢复前不能支撑加仓、追高、加融资或自动交易。"
                    if blocked
                    else f"{provider} 未实时验证前，只能作为辅助证据。"
                ),
                "items": provider_rows[:4],
                "recovery_action": recovery_action,
                "deepseek_called": False,
                "external_call_policy": "not_triggered",
            }
        )
    blocked_count = sum(card["blocked_count"] for card in provider_cards)
    manual_count = sum(card["manual_count"] for card in provider_cards)
    stale_count = sum(card["stale_count"] for card in provider_cards)
    available_count = sum(card["available_count"] for card in provider_cards)
    if blocked_count:
        status = "blocked"
        tone = "failed"
        headline = f"Provider 数据能力有 {blocked_count} 个阻断项"
    elif manual_count or stale_count:
        status = "partial"
        tone = "stale"
        headline = f"Provider 数据能力有 {manual_count + stale_count} 个待手动/待复核项"
    elif available_count:
        status = "ready"
        tone = "ready"
        headline = "Provider 数据能力当前可辅助验证"
    else:
        status = "missing"
        tone = "missing"
        headline = "Provider 数据能力待检测"
    return {
        "title": "数据源能力驾驶舱",
        "status": status,
        "tone": tone,
        "headline": headline,
        "summary": f"Tushare / AkShare / yfinance / Supabase｜可用 {available_count}｜受限 {blocked_count}｜需手动 {manual_count}｜缓存/待验证 {stale_count}",
        "providers": provider_cards,
        "recovery_actions": [
            card["recovery_action"]
            for card in provider_cards
            if card["status"] != "ready"
        ],
        "safe_mode_text": "这里只读取本地数据能力 packet 和健康账本；不会自动调用 Tushare、AkShare、yfinance、Supabase、DeepSeek、回测或全市场扫描。",
        "deepseek_called": False,
        "external_call_policy": "not_triggered",
    }


def _legacy_gap_item_message(item: Mapping[str, Any]) -> str:
    label = _to_text(item.get("label"), "旧版 A股能力")
    recovery_state = _to_text(item.get("recovery_state"), "waiting")
    status_label = _to_text(item.get("status_label"), "待验证")
    if recovery_state == "recovered":
        return f"{label}已回流，可进入综合中心证据链；仍需复核交易日、来源和风险纪律。"
    if recovery_state == "blocked":
        return f"{label}当前为{status_label}，不能把缺失数据当成无风险。"
    return f"{label}待验证；保持安全空态或缓存观察，需要时手动检测。"


def _legacy_gap_diagnostic(item: Mapping[str, Any]) -> dict:
    key = _to_text(item.get("key"))
    config = LEGACY_A_SHARE_GAP_DIAGNOSTICS.get(key, {})
    label = _to_text(item.get("label"), "旧版 A股能力")
    writes_packet = _to_text(item.get("writes_packet"), "command_center_packet")
    return {
        "why_not_found": _to_text(
            config.get("why_not_found"),
            f"{label}可能因为权限、交易日更新、近期无数据或缓存过期而暂不可见。",
        ),
        "manual_recovery_steps": _as_list(config.get("manual_recovery_steps"))
        or [
            f"进入{_to_text(item.get('toolbox_entry'), '高级工具箱')}",
            f"点击“{_to_text(item.get('action_label'), '手动检测')}”",
            f"成功后写回 {writes_packet}，再回到综合中心复核。",
        ],
        "button_context": _to_text(
            config.get("button_context"),
            f"只检测 {label} 并写回 {writes_packet}；不会自动调用 DeepSeek 或重型接口。",
        ),
        "decision_guardrail": _to_text(
            config.get("decision_guardrail"),
            f"缺少{label}时，不能把数据缺口当成无风险或已验证结论。",
        ),
    }


def _legacy_gap_diagnostic_for_writes_packet(writes_packet: str, label: str = "") -> dict:
    key = LEGACY_A_SHARE_GAP_WRITES_TO_KEY.get(_to_text(writes_packet))
    if not key:
        return {}
    return _legacy_gap_diagnostic(
        {
            "key": key,
            "label": label or A_SHARE_FACT_RECOVERY_SOURCES[0]["label"],
            "writes_packet": writes_packet,
            "action_label": TOOL_RECOVERY_MANUAL_CHECKS.get(writes_packet, {}).get("button_label"),
            "toolbox_entry": _legacy_a_share_fact_legacy_tab(key, writes_packet),
        }
    )


def build_legacy_a_share_gap_summary(snapshot: Any = None) -> dict:
    payload = _as_mapping(snapshot)
    recovery_summary = _as_mapping(payload.get("a_share_fact_recovery_summary"))
    if not recovery_summary:
        recovery_summary = build_a_share_fact_recovery_summary(payload)
    items = [
        _as_mapping(item)
        for item in _as_list(recovery_summary.get("items"))
        if _as_mapping(item).get("key") in LEGACY_A_SHARE_GAP_KEYS
    ]
    for item in items:
        item["message"] = _legacy_gap_item_message(item)
        item.update(_legacy_gap_diagnostic(item))
        item["is_recovered"] = item.get("recovery_state") == "recovered"
        item["requires_manual"] = item.get("refresh_policy") == "button_gated"
        item["deepseek_called"] = False
    recovered = [item for item in items if item.get("recovery_state") == "recovered"]
    blocked = [item for item in items if item.get("recovery_state") == "blocked"]
    waiting = [item for item in items if item.get("recovery_state") == "waiting"]
    if blocked:
        tone = "failed"
        headline = f"旧能力缺口：仍受限 {len(blocked)} 项"
        next_action = f"优先处理 {blocked[0]['label']}；只切换到高级工具箱，不自动请求 Tushare。"
    elif waiting:
        tone = "missing" if not recovered else "stale"
        headline = f"旧能力缺口：待验证 {len(waiting)} 项"
        next_action = f"需要时手动检测 {waiting[0]['label']}；页面打开不会自动请求 Tushare。"
    else:
        tone = "ready"
        headline = "旧能力缺口已回流"
        next_action = "涨跌停/情绪、筹码/胜率已形成 packet；执行前仍需复核交易日和来源。"
    return {
        "title": "旧能力缺口：涨跌停/情绪 · 筹码/胜率",
        "tone": tone,
        "headline": headline,
        "summary": f"已回流 {len(recovered)}｜仍受限 {len(blocked)}｜待验证 {len(waiting)}",
        "items": items,
        "next_action": next_action,
        "safe_mode_text": "这里只读取本地 packet 和恢复总账；不会自动调用 Tushare、DeepSeek、回测或全市场扫描。",
        "deepseek_called": False,
    }


TOOL_RECOVERY_CONFIG = {
    "radar_packet": {
        "key": "next_ticket_radar",
        "label": "下一票雷达",
        "action_label": "手动运行下一票雷达",
        "toolbox_entry": "高级工具箱 / 下一票雷达",
        "legacy_tab": "下一票雷达",
        "writes_packet": "command_center_radar_packet",
        "reason": "候选池来自缓存或手动扫描；缺失时不能把空候选当作无机会。",
    },
    "etf_packet": {
        "key": "margin_etf",
        "label": "融资 ETF",
        "action_label": "手动刷新 ETF 配置/日线",
        "toolbox_entry": "高级工具箱 / 融资 ETF",
        "legacy_tab": "融资 ETF",
        "writes_packet": "command_center_etf_packet",
        "reason": "ETF 配置和赛道强弱来自本地快照；缺失时不能放大融资或追高。",
    },
    "discipline_packet": {
        "key": "discipline_backtest",
        "label": "交易纪律/回测",
        "action_label": "手动运行回测或读取纪律缓存",
        "toolbox_entry": "高级工具箱 / 交易纪律实验室",
        "legacy_tab": "交易纪律实验室",
        "writes_packet": "command_center_discipline_packet",
        "reason": "回测必须按钮触发；缺少纪律缓存时只能观察或降风险。",
    },
    "quant_packet": {
        "key": "quant_projection",
        "label": "量化推演",
        "action_label": "手动生成量化推演",
        "toolbox_entry": "高级工具箱 / 量化推演",
        "legacy_tab": "量化推演",
        "writes_packet": "command_center_quant_packet",
        "reason": "完整量化推演和回测必须手动触发；缺失时不能把评分写成事实。",
    },
}


def _tool_recovery_priority(packet: Mapping[str, Any]) -> int:
    status = _to_text(packet.get("status"), "waiting")
    data_status = _to_text(packet.get("data_status") or packet.get("cache_state"), "missing")
    if status == "failed":
        return 1
    if data_status == "missing" or status in {"waiting", "missing"}:
        return 2
    if data_status in {"cached", "stale"} or status == "partial":
        return 3
    return 4


def _tool_needs_recovery(packet: Mapping[str, Any]) -> bool:
    status = _to_text(packet.get("status"), "waiting")
    data_status = _to_text(packet.get("data_status") or packet.get("cache_state"), "missing")
    if status == "failed":
        return True
    if data_status in {"missing", "cached", "stale"}:
        return True
    return status in {"waiting", "missing", "partial"}


def build_tool_recovery_actions_snapshot(snapshot: Any = None, limit: int = MAX_CAPABILITY_ITEMS) -> list[dict]:
    payload = _as_mapping(snapshot)
    actions = []
    for packet_key, config in TOOL_RECOVERY_CONFIG.items():
        packet = _as_mapping(payload.get(packet_key))
        if not packet or not _tool_needs_recovery(packet):
            continue
        label = config["label"]
        legacy_tab = config["legacy_tab"]
        actions.append(
            {
                "key": config["key"],
                "label": label,
                "status": _to_text(packet.get("status"), "waiting"),
                "data_status": _to_text(packet.get("data_status") or packet.get("cache_state"), "missing"),
                "priority": _tool_recovery_priority(packet),
                "reason": _to_text(packet.get("manual_required_text") or packet.get("backtest_required_text") or config["reason"]),
                "action_label": config["action_label"],
                "toolbox_entry": config["toolbox_entry"],
                "workspace_target": "高级工具箱（旧版保留）",
                "workspace_state_key": "workspace_mode_v2",
                "legacy_tab": legacy_tab,
                "legacy_tab_state_key": "legacy_workspace_selected_tab",
                "navigation_label": f"主导航切到高级工具箱（旧版保留）→ 高级工具模块选择{legacy_tab}",
                "writes_packet": config["writes_packet"],
                "refresh_policy": "button_gated",
                "deepseek_called": False,
            }
        )
    actions = sorted(actions, key=lambda item: (item["priority"], item["label"]))
    return actions[: max(1, int(limit or MAX_CAPABILITY_ITEMS))]


def build_next_ticket_evidence_recovery_actions_snapshot(
    snapshot: Any = None,
    limit: int = MAX_CAPABILITY_ITEMS,
) -> list[dict]:
    payload = _as_mapping(snapshot)
    candidates = _as_list(payload.get("next_ticket_candidates"))
    if not candidates and _as_mapping(payload.get("radar_packet")).get("top_candidates"):
        candidates = _as_list(_as_mapping(payload.get("radar_packet")).get("top_candidates"))
    actions_by_packet: dict[str, dict] = {}
    for candidate in candidates:
        item = _as_mapping(candidate)
        if not item:
            continue
        ticker = _to_text(item.get("ticker") or item.get("name"), "候选")
        name = _to_text(item.get("name"))
        brief = _as_mapping(item.get("decision_brief"))
        missing_labels = set(_to_text(label) for label in _as_list(brief.get("missing_evidence")))
        blocking_labels = set(_to_text(label) for label in _as_list(brief.get("blocking_evidence")))
        for evidence in _as_list(item.get("evidence_chain")):
            row = _as_mapping(evidence)
            if not row:
                continue
            status = _to_text(row.get("status"))
            if status not in {"missing", "cached", "blocked", "failed"}:
                continue
            label = _to_text(row.get("label"), "候选证据")
            if missing_labels and label not in missing_labels and status in {"missing", "cached"}:
                continue
            writes_packet = _to_text(row.get("writes_packet"), "command_center_packet")
            if not writes_packet:
                continue
            legacy_tab = _legacy_a_share_fact_legacy_tab(row.get("key"), writes_packet)
            action = actions_by_packet.setdefault(
                writes_packet,
                {
                    "key": f"next_ticket_evidence:{_to_text(row.get('key'), writes_packet)}",
                    "label": label,
                    "status": status,
                    "status_label": _to_text(row.get("status_label"), "待补证"),
                    "priority": 1 if status in {"blocked", "failed"} or label in blocking_labels else 2,
                    "reason": f"下一票候选需要补齐{label}，否则不能升级为作战准备依据。",
                    "diagnostic_answer": f"{label}证据来自旧工作台能力；缺失时候选只能保持待验证或只观察。",
                    "interface_diagnostic_answer": f"{label}证据未回流到 {writes_packet}，可能是权限、近期无数据、缓存或尚未手动运行旧工具。",
                    "decision_guardrail": f"{label}未验证前，下一票候选不能作为买入、追高或加融资依据。",
                    "action_label": f"手动补齐{label}证据",
                    "toolbox_entry": f"高级工具箱 / {legacy_tab}",
                    "workspace_target": "高级工具箱（旧版保留）",
                    "workspace_state_key": "workspace_mode_v2",
                    "legacy_tab": legacy_tab,
                    "legacy_tab_state_key": "legacy_workspace_selected_tab",
                    "navigation_label": f"主导航切到高级工具箱（旧版保留）→ 高级工具模块选择{legacy_tab}；手动执行后回流 {writes_packet}。",
                    "writes_packet": writes_packet,
                    "refresh_policy": "button_gated",
                    "recovery_button_context": f"这里只打开“{legacy_tab}”入口补齐{label}证据；不会自动运行扫描、DeepSeek、回测或重型数据接口。",
                    "candidate_refs": [],
                    "deepseek_called": False,
                },
            )
            ref = f"{ticker} {name}".strip()
            refs = action.setdefault("candidate_refs", [])
            if ref not in refs:
                refs.append(ref)
            action["reason"] = f"{label}待补证影响：{'、'.join(refs[:3])}。缺失时候选不能升级为作战准备依据。"
            if status in {"blocked", "failed"}:
                action["priority"] = 1
                action["status"] = status
                action["status_label"] = _to_text(row.get("status_label"), "阻断")
    actions = sorted(actions_by_packet.values(), key=lambda item: (item["priority"], item["label"]))
    return actions[: max(1, int(limit or MAX_CAPABILITY_ITEMS))]


def _legacy_a_share_fact_priority(action: Mapping[str, Any]) -> int:
    state = _to_text(action.get("state") or action.get("status"), "waiting")
    if state in {"failed", "error", "permission_denied", "权限不足", "失败"}:
        return 1
    if state in {"cached", "stale", "partial", "using_cache", "使用缓存"}:
        return 2
    return 3


def _legacy_a_share_fact_legacy_tab(key: Any = "", writes_packet: Any = "") -> str:
    text = _to_text(key) or _to_text(writes_packet)
    return {
        "dragon_tiger": "下一票雷达",
        "command_center_dragon_tiger_packet": "下一票雷达",
        "margin": "融资 ETF",
        "command_center_margin_packet": "融资 ETF",
        "moneyflow": "今日关注池",
        "command_center_moneyflow_packet": "今日关注池",
        "limit_emotion": "数据源体检",
        "command_center_limit_emotion_packet": "数据源体检",
        "chip_radar": "量化推演",
        "command_center_chip_packet": "量化推演",
        "hard_risk": "天眼风控",
        "command_center_hard_risk_packet": "天眼风控",
    }.get(text, "今日关注池")


def _legacy_a_share_fact_recovery_actions_from_view(view_model: Any = None) -> list[dict]:
    payload = _as_mapping(view_model)
    entries = _as_list(payload.get("cards")) + _as_list(payload.get("sections"))
    actions = []
    for entry in entries:
        item = _as_mapping(entry)
        action = _as_mapping(item.get("recovery_action"))
        if not action or _to_text(action.get("refresh_policy")) == "not_needed":
            continue
        key = _to_text(action.get("key") or item.get("key"))
        writes_packet = _to_text(action.get("writes_packet"), "command_center_packet")
        toolbox_entry = _to_text(action.get("toolbox_entry"), "高级工具箱")
        legacy_tab = _legacy_a_share_fact_legacy_tab(key, writes_packet)
        actions.append(
            {
                "key": f"legacy_a_share_fact:{key or writes_packet}",
                "label": _to_text(action.get("label") or item.get("label") or item.get("title"), "A股事实卡"),
                "status": _to_text(action.get("state") or item.get("status"), "waiting"),
                "status_label": _to_text(action.get("status_label") or item.get("status"), "待验证"),
                "priority": _legacy_a_share_fact_priority(action),
                "reason": _to_text(action.get("reason") or item.get("message"), "旧版 A股事实卡仍待手动恢复。"),
                "action_label": _to_text(action.get("action_label"), "手动刷新 A股事实卡"),
                "toolbox_entry": toolbox_entry,
                "workspace_target": "高级工具箱（旧版保留）",
                "workspace_state_key": "workspace_mode_v2",
                "legacy_tab": legacy_tab,
                "legacy_tab_state_key": "legacy_workspace_selected_tab",
                "navigation_label": f"主导航切到高级工具箱（旧版保留）→ 高级工具模块选择{legacy_tab}；手动执行后回流 {writes_packet}。",
                "writes_packet": writes_packet,
                "refresh_policy": "button_gated",
                "source_label": "旧版 A股事实卡",
                "deepseek_called": False,
            }
        )
    return actions


def build_legacy_a_share_fact_recovery_actions_snapshot(
    snapshot: Any = None,
    limit: int = MAX_CAPABILITY_ITEMS,
) -> list[dict]:
    payload = _as_mapping(snapshot)
    primary_view = legacy_a_share_gate_service.build_legacy_a_share_primary_fact_cards(
        dragon_tiger_packet=payload.get("dragon_tiger_packet") or payload.get("command_center_dragon_tiger_packet"),
        margin_packet=payload.get("margin_packet") or payload.get("command_center_margin_packet"),
        moneyflow_packet=payload.get("moneyflow_packet") or payload.get("command_center_moneyflow_packet"),
    )
    secondary_view = legacy_a_share_gate_service.build_legacy_a_share_secondary_fact_sections(
        limit_emotion_packet=payload.get("limit_emotion_packet") or payload.get("command_center_limit_emotion_packet"),
        chip_packet=payload.get("chip_packet") or payload.get("command_center_chip_packet"),
    )
    actions = (
        _legacy_a_share_fact_recovery_actions_from_view(primary_view)
        + _legacy_a_share_fact_recovery_actions_from_view(secondary_view)
    )
    deduped = []
    seen = set()
    for action in sorted(actions, key=lambda item: (item["priority"], item["label"])):
        writes_packet = action.get("writes_packet")
        if writes_packet in seen:
            continue
        seen.add(writes_packet)
        deduped.append(action)
    return deduped[: max(1, int(limit or MAX_CAPABILITY_ITEMS))]


def _normalize_recovery_center_action(
    action: Any = None,
    source_type: str = "",
    source_label: str = "",
    default_priority: int = 3,
) -> dict:
    item = _as_mapping(action)
    if not item:
        return {}
    label = _to_text(item.get("label"), "数据能力")
    writes_packet = _to_text(item.get("writes_packet"), "command_center_packet")
    status = _to_text(item.get("status") or item.get("state") or item.get("data_status"), "waiting")
    legacy_tab = _to_text(item.get("legacy_tab"), _recovery_legacy_tab(writes_packet, item.get("key") or item.get("api")))
    return {
        "key": _to_text(item.get("key") or item.get("api") or writes_packet or label),
        "label": label,
        "source_type": _to_text(source_type, "recovery"),
        "source_label": _to_text(source_label, "恢复队列"),
        "status": status,
        "status_label": _to_text(item.get("status_label") or item.get("capability_label"), "待验证"),
        "priority": int(_to_number(item.get("priority")) or default_priority),
        "reason": _to_text(item.get("reason") or item.get("action_hint"), f"{label}仍待验证。"),
        "diagnostic_answer": _to_text(item.get("diagnostic_answer") or item.get("meaning"), f"{label}仍需核对接口状态、日期和覆盖范围。"),
        "interface_diagnostic_answer": _to_text(item.get("interface_diagnostic_answer") or item.get("diagnostic_answer") or item.get("meaning"), f"{label}仍需核对接口状态、日期和覆盖范围。"),
        "decision_guardrail": _to_text(item.get("decision_guardrail"), f"{label}未恢复前不能作为加仓、追高或加融资依据。"),
        "action_label": _to_text(item.get("action_label"), f"手动恢复{label}"),
        "toolbox_entry": _to_text(item.get("toolbox_entry") or item.get("advanced_entry"), "高级工具箱"),
        "workspace_target": _to_text(item.get("workspace_target"), "高级工具箱（旧版保留）"),
        "workspace_state_key": _to_text(item.get("workspace_state_key"), "workspace_mode_v2"),
        "legacy_tab_state_key": _to_text(item.get("legacy_tab_state_key"), "legacy_workspace_selected_tab"),
        "navigation_label": _to_text(
            item.get("navigation_label"),
            f"主导航切到高级工具箱（旧版保留）→ 高级工具模块选择{legacy_tab}；手动执行后回流 {writes_packet}。",
        ),
        "legacy_tab": legacy_tab,
        "writes_packet": writes_packet,
        "refresh_policy": _to_text(item.get("refresh_policy"), "button_gated"),
        "recovery_button_context": _to_text(
            item.get("recovery_button_context") or item.get("button_context"),
            f"按钮只恢复 {label} 并回流 {writes_packet}；不会自动调用 DeepSeek、回测或全市场扫描。",
        ),
        "deepseek_called": False,
    }


RECOVERY_PRIORITY_LANES = (
    {
        "key": "p0",
        "label": "P0 权限/本会话跳过",
        "tone": "failed",
        "next_action": "先确认 Tushare 权限、积分、网络或本会话跳过标记；不要把权限缺口当作行情不存在。",
    },
    {
        "key": "p1",
        "label": "P1 缓存/近期无数据",
        "tone": "stale",
        "next_action": "复核交易日、缓存日期和接口覆盖范围；缓存只能防白屏，不能当作实时事实。",
    },
    {
        "key": "p2",
        "label": "P2 旧工具 packet 迁移",
        "tone": "missing",
        "next_action": "把旧工作台能力手动恢复成 command_center packet，再回到综合中心验证。",
    },
)


def _recovery_action_lane_key(action: Mapping[str, Any]) -> str:
    status_text = " ".join(
        _to_text(action.get(key))
        for key in (
            "status",
            "status_label",
            "reason",
            "diagnostic_answer",
            "source_type",
            "source_label",
            "writes_packet",
        )
    ).lower()
    if any(
        token in status_text
        for token in (
            "permission_denied",
            "disabled_this_session",
            "network_failed",
            "not_configured",
            "failed",
            "error",
            "权限不足",
            "本会话跳过",
            "受限",
            "失败",
        )
    ):
        return "p0"
    if any(
        token in status_text
        for token in (
            "empty_recent",
            "stale_cache",
            "fallback_used",
            "using_cache",
            "cached",
            "缓存",
            "近期无",
            "暂无数据",
            "暂无当日",
            "替代口径",
        )
    ):
        return "p1"
    if action.get("source_type") in {"legacy_tool", "legacy_migration", "a_share_fact"}:
        return "p2"
    return "p1"


def build_recovery_priority_lanes(actions: Any = None) -> list[dict]:
    action_list = [_as_mapping(item) for item in _as_list(actions)]
    action_list = [item for item in action_list if item]
    lanes = []
    for lane_config in RECOVERY_PRIORITY_LANES:
        lane_items = [
            item
            for item in action_list
            if _recovery_action_lane_key(item) == lane_config["key"]
        ]
        lanes.append(
            {
                "key": lane_config["key"],
                "label": lane_config["label"],
                "tone": lane_config["tone"],
                "count": len(lane_items),
                "items": lane_items[:3],
                "summary": (
                    "、".join(_to_text(item.get("label"), "恢复项") for item in lane_items[:3])
                    if lane_items
                    else "暂无"
                ),
                "next_action": lane_config["next_action"],
            }
        )
    return lanes


DECISION_PRIORITY_QUEUE_CONFIG = {
    "p0": {
        "rank": 1,
        "priority_label": "P0 阻断交易判断",
        "tone": "failed",
        "decision_mode": "阻断加仓",
        "why_first": "权限、本会话跳过、网络或配置问题会让关键证据不可用，不能把缺口当成行情不存在。",
        "fallback_impact": "未恢复前，不支持加仓、追高、加融资或把风险写成已排除。",
    },
    "p1": {
        "rank": 2,
        "priority_label": "P1 执行前验证",
        "tone": "stale",
        "decision_mode": "谨慎验证",
        "why_first": "缓存、替代口径或近期无记录只能防白屏，不能当作实时已验证事实。",
        "fallback_impact": "执行前必须复核交易日、缓存时间、标的覆盖和接口口径。",
    },
    "p2": {
        "rank": 3,
        "priority_label": "P2 能力回流补强",
        "tone": "missing",
        "decision_mode": "补强证据链",
        "why_first": "旧工具能力未回流时，综合中心只能展示待验证或上次成功结果。",
        "fallback_impact": "不阻断看盘，但不能把旧工具缺失项当作已验证依据。",
    },
}


def build_decision_priority_queue(actions: Any = None, limit: int = MAX_CAPABILITY_ITEMS) -> list[dict]:
    action_list = [_as_mapping(item) for item in _as_list(actions)]
    action_list = [item for item in action_list if item]
    rows = []
    seen = set()
    for action in action_list:
        lane_key = _recovery_action_lane_key(action)
        config = DECISION_PRIORITY_QUEUE_CONFIG.get(lane_key, DECISION_PRIORITY_QUEUE_CONFIG["p1"])
        writes_packet = _to_text(action.get("writes_packet"), "command_center_packet")
        dedupe_key = (lane_key, writes_packet, _to_text(action.get("label")))
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        label = _to_text(action.get("label"), "恢复项")
        diagnostic = _to_text(
            action.get("interface_diagnostic_answer")
            or action.get("diagnostic_answer")
            or action.get("reason"),
            f"{label}仍需核对接口状态、日期和覆盖范围。",
        )
        rows.append(
            {
                "key": f"{lane_key}:{writes_packet or _to_text(action.get('key'), 'recovery')}",
                "lane_key": lane_key,
                "rank": config["rank"],
                "priority_label": config["priority_label"],
                "tone": _to_text(action.get("tone"), config["tone"]),
                "decision_mode": config["decision_mode"],
                "label": label,
                "status": _to_text(action.get("status"), "waiting"),
                "status_label": _to_text(action.get("status_label"), "待验证"),
                "diagnostic_answer": diagnostic,
                "decision_impact": _to_text(action.get("decision_guardrail") or action.get("decision_impact"), config["fallback_impact"]),
                "why_first": config["why_first"],
                "action_label": _to_text(action.get("action_label"), f"手动恢复{label}"),
                "navigation_label": _to_text(action.get("navigation_label"), "从首页恢复队列进入对应手动工具。"),
                "workspace_target": _to_text(action.get("workspace_target"), "高级工具箱（旧版保留）"),
                "workspace_state_key": _to_text(action.get("workspace_state_key"), "workspace_mode_v2"),
                "legacy_tab_state_key": _to_text(action.get("legacy_tab_state_key"), "legacy_workspace_selected_tab"),
                "legacy_tab": _to_text(action.get("legacy_tab")),
                "writes_packet": writes_packet,
                "refresh_policy": _to_text(action.get("refresh_policy"), "button_gated"),
                "recovery_button_context": _to_text(
                    action.get("recovery_button_context") or action.get("button_context"),
                    f"按钮只恢复 {label} 并回流 {writes_packet}；不会自动调用 DeepSeek、回测或全市场扫描。",
                ),
                "recovery_result_status": _to_text(action.get("recovery_result_status"), "waiting"),
                "recovery_result_status_label": _to_text(action.get("recovery_result_status_label"), "待验证"),
                "recovery_result_tone": _to_text(action.get("recovery_result_tone"), "missing"),
                "recovery_result_message": _to_text(
                    action.get("recovery_result_message"),
                    "尚未检测到本项恢复结果回流。",
                ),
                "recovery_result_updated_at": _to_text(action.get("recovery_result_updated_at"), "暂无"),
                "recovery_result_source": _to_text(action.get("recovery_result_source"), "本地恢复状态"),
                "deepseek_called": False,
            }
        )
    rows = sorted(rows, key=lambda item: (item["rank"], item["label"], item["writes_packet"]))
    return rows[: max(1, int(limit or MAX_CAPABILITY_ITEMS))]


def _recovery_result_lookup_from_state(state: Any = None) -> dict[str, dict]:
    payload = _as_mapping(state)
    lookup = {}

    def add_item(raw: Any = None) -> None:
        item = _as_mapping(raw)
        if not item:
            return
        writes_packet = _to_text(item.get("writes_packet"))
        if not writes_packet or writes_packet in lookup:
            return
        lookup[writes_packet] = {
            "status": _to_text(item.get("status"), "waiting"),
            "status_label": _to_text(item.get("status_label"), "待验证"),
            "tone": _to_text(item.get("tone"), "missing"),
            "message": _to_text(item.get("message"), "恢复结果待验证。"),
            "updated_at": _to_text(item.get("updated_at"), "暂无"),
            "source": _to_text(item.get("source"), "本地恢复状态"),
            "packet_key": _to_text(item.get("packet_key"), writes_packet),
            "next_action": _to_text(item.get("next_action"), "按恢复队列手动处理。"),
            "external_call_policy": _to_text(item.get("external_call_policy"), "not_triggered"),
            "deepseek_called": False,
        }

    timeline = (
        _as_mapping(payload.get("command_center_recovery_result_timeline"))
        or _as_mapping(payload.get("recovery_result_timeline"))
    )
    for raw in _as_list(timeline.get("items")):
        add_item(raw)

    strip = _as_mapping(payload.get("recovery_result_status_strip"))
    if not strip and _as_mapping(payload.get("latest_recovery_result_notice")):
        strip = build_recovery_result_status_strip(payload)
    for raw in _as_list(strip.get("items")):
        add_item(raw)

    latest = _as_mapping(payload.get("latest_recovery_result_notice"))
    if latest:
        add_item(latest)
    return lookup


def _fallback_recovery_result_item(action: Mapping[str, Any], state: Any = None) -> dict:
    payload = _as_mapping(state)
    writes_packet = _to_text(action.get("writes_packet"), "command_center_packet")
    packet_key, packet = _resolve_recovery_packet(payload, writes_packet)
    if packet:
        display_state = _recovery_display_state(
            packet,
            writes_packet,
            fallback_status=action.get("status"),
        )
        label = _to_text(action.get("label"), "恢复项")
        status = display_state["status"]
        if status == "recovered":
            message = f"{label} 已回流到 {writes_packet}；综合中心可读取这项结构化结果。"
        elif status == "cached":
            message = f"{label} 当前读取到缓存；执行前仍需复核日期、来源和覆盖口径。"
        elif status == "blocked":
            message = f"{label} 仍未形成可用回流；不能把缺失数据当成安全信号。"
        else:
            message = f"{label} 尚未检测到可读回流；需要在高级工具箱手动运行按钮。"
        return {
            "status": status,
            "status_label": display_state["label"],
            "tone": display_state["tone"],
            "message": message,
            "updated_at": _to_text(
                packet.get("updated_at")
                or packet.get("generated_at")
                or packet.get("checked_at"),
                "暂无",
            ),
            "source": _to_text(packet.get("source"), "本地恢复状态"),
            "packet_key": packet_key,
            "next_action": "返回综合推演中心查看 Home Action Snapshot。",
            "external_call_policy": "not_triggered",
            "deepseek_called": False,
        }
    return {
        "status": "waiting",
        "status_label": "待验证",
        "tone": "missing",
        "message": "尚未检测到本项恢复结果回流。",
        "updated_at": "暂无",
        "source": "本地恢复状态",
        "packet_key": writes_packet,
        "next_action": "按恢复队列手动处理；页面打开不会自动请求外部接口。",
        "external_call_policy": "not_triggered",
        "deepseek_called": False,
    }


def attach_recovery_result_status_to_action(
    action: Any = None,
    state: Any = None,
    result_lookup: Any = None,
) -> dict:
    item = _as_mapping(action)
    if not item:
        return {}
    lookup = _as_mapping(result_lookup)
    writes_packet = _to_text(item.get("writes_packet"), "command_center_packet")
    result = _as_mapping(lookup.get(writes_packet)) or _fallback_recovery_result_item(item, state)
    item["recovery_result_status"] = _to_text(result.get("status"), "waiting")
    item["recovery_result_status_label"] = _to_text(result.get("status_label"), "待验证")
    item["recovery_result_tone"] = _to_text(result.get("tone"), "missing")
    item["recovery_result_message"] = _to_text(result.get("message"), "尚未检测到本项恢复结果回流。")
    item["recovery_result_updated_at"] = _to_text(result.get("updated_at"), "暂无")
    item["recovery_result_source"] = _to_text(result.get("source"), "本地恢复状态")
    item["recovery_result_packet_key"] = _to_text(result.get("packet_key"), writes_packet)
    item["recovery_result_next_action"] = _to_text(result.get("next_action"), "按恢复队列手动处理。")
    item["recovery_result_external_call_policy"] = _to_text(result.get("external_call_policy"), "not_triggered")
    item["deepseek_called"] = False
    return item


def attach_next_ticket_evidence_recovery_results(snapshot: Any = None) -> dict:
    payload = _as_mapping(snapshot)
    candidates = []
    for raw_candidate in _as_list(payload.get("next_ticket_candidates")):
        candidate = _as_mapping(raw_candidate)
        if not candidate:
            continue
        evidence_rows = []
        counts = {"recovered": 0, "cached": 0, "blocked": 0, "waiting": 0}
        for raw_evidence in _as_list(candidate.get("evidence_chain")):
            evidence = _as_mapping(raw_evidence)
            if not evidence:
                continue
            writes_packet = _to_text(evidence.get("writes_packet"))
            label = _to_text(evidence.get("label"), "证据")
            if writes_packet:
                result = _fallback_recovery_result_item(
                    {
                        "writes_packet": writes_packet,
                        "label": label,
                        "status": evidence.get("status"),
                    },
                    payload,
                )
                status = _to_text(result.get("status"), "waiting")
                evidence["recovery_result_status"] = status
                evidence["recovery_result_status_label"] = _to_text(result.get("status_label"), "待验证")
                evidence["recovery_result_tone"] = _to_text(result.get("tone"), "missing")
                evidence["recovery_result_message"] = _to_text(result.get("message"), f"{label}恢复结果待验证。")
                evidence["recovery_result_updated_at"] = _to_text(result.get("updated_at"), "暂无")
                evidence["recovery_result_source"] = _to_text(result.get("source"), "本地恢复状态")
                evidence["recovery_result_packet_key"] = _to_text(result.get("packet_key"), writes_packet)
                evidence["recovery_result_external_call_policy"] = _to_text(result.get("external_call_policy"), "not_triggered")
            else:
                status = "waiting"
                evidence["recovery_result_status"] = "waiting"
                evidence["recovery_result_status_label"] = "待验证"
                evidence["recovery_result_tone"] = "missing"
                evidence["recovery_result_message"] = f"{label}尚未绑定回流 packet。"
                evidence["recovery_result_external_call_policy"] = "not_triggered"
            if status in {"recovered", "cached", "blocked"}:
                counts[status] += 1
            else:
                counts["waiting"] += 1
            evidence["deepseek_called"] = False
            evidence_rows.append(evidence)
        candidate["evidence_chain"] = evidence_rows
        candidate["evidence_recovery_items"] = [
            {
                "label": _to_text(item.get("label"), "证据"),
                "status": _to_text(item.get("recovery_result_status"), "waiting"),
                "status_label": _to_text(item.get("recovery_result_status_label"), "待验证"),
                "tone": _to_text(item.get("recovery_result_tone"), "missing"),
                "writes_packet": _to_text(item.get("writes_packet")),
                "message": _to_text(item.get("recovery_result_message"), "恢复结果待验证。"),
                "deepseek_called": False,
            }
            for item in evidence_rows
        ]
        candidate["evidence_recovery_summary"] = (
            f"已回流 {counts['recovered']}｜使用缓存 {counts['cached']}｜仍阻断 {counts['blocked']}｜待验证 {counts['waiting']}"
            if evidence_rows
            else "证据恢复结果待验证"
        )
        if counts["blocked"]:
            impact_status = "blocked"
            impact_label = "仍不可执行"
            impact_tone = "failed"
            impact_text = "存在阻断证据未恢复，候选不能升级为作战准备。"
        elif counts["waiting"] or counts["cached"]:
            impact_status = "still_verify"
            impact_label = "仍等验证"
            impact_tone = "stale"
            impact_text = "证据链仍未完全实时验证，候选保持等验证/只观察。"
        elif counts["recovered"]:
            impact_status = "recovered"
            impact_label = "证据已回流"
            impact_tone = "ready"
            impact_text = "核心证据已回流；仍需触发条件、纪律和风险预算共同确认。"
        else:
            impact_status = "waiting"
            impact_label = "待验证"
            impact_tone = "missing"
            impact_text = "尚未形成可判断的候选证据恢复结果。"
        candidate["evidence_recovery_impact"] = {
            "status": impact_status,
            "label": impact_label,
            "tone": impact_tone,
            "summary": candidate["evidence_recovery_summary"],
            "impact_text": impact_text,
            "deepseek_called": False,
            "external_call_policy": "not_triggered",
        }
        decision_brief = _as_mapping(candidate.get("decision_brief"))
        if decision_brief:
            decision_brief["recovery_impact_label"] = impact_label
            decision_brief["recovery_impact_text"] = impact_text
            decision_brief["recovery_impact_tone"] = impact_tone
            decision_brief["external_call_policy"] = "not_triggered"
            decision_brief["deepseek_called"] = False
            candidate["decision_brief"] = decision_brief
        candidates.append(candidate)
    payload["next_ticket_candidates"] = candidates
    return payload


ETF_EVIDENCE_WRITES_PACKET = {
    "tracking_index": "command_center_etf_packet",
    "liquidity": "command_center_etf_packet",
    "overlap": "command_center_etf_packet",
    "overheat": "command_center_etf_packet",
    "margin_cash": "command_center_margin_packet",
}


def _etf_evidence_recovery_status(evidence: Mapping[str, Any], payload: Mapping[str, Any]) -> dict:
    key = _to_text(evidence.get("key"))
    label = _to_text(evidence.get("label"), "ETF 证据")
    writes_packet = _to_text(evidence.get("writes_packet"), ETF_EVIDENCE_WRITES_PACKET.get(key, "command_center_etf_packet"))
    packet_result = _fallback_recovery_result_item(
        {
            "writes_packet": writes_packet,
            "label": label,
            "status": evidence.get("status"),
        },
        payload,
    )
    packet_status = _to_text(packet_result.get("status"), "waiting")
    evidence_status = _to_text(evidence.get("status"), "missing")
    if packet_status == "blocked":
        status = "blocked"
        status_label = _to_text(packet_result.get("status_label"), "仍阻断")
        tone = "failed"
        message = f"{label}对应回流仍不可用；ETF 不能据此放大融资或追高。"
    elif evidence_status == "ready":
        status = "verified"
        status_label = "已验证"
        tone = "ready"
        message = f"{label}已形成可读证据；执行前仍需和风险预算一起复核。"
    elif evidence_status in {"stale", "failed"} or packet_status == "cached":
        status = "review"
        status_label = "需复核"
        tone = "stale"
        message = f"{label}仍需复核日期、口径或风险边界。"
    else:
        status = "waiting"
        status_label = "待验证"
        tone = "missing"
        message = f"{label}尚未形成可执行证据；只能观察，不放大仓位。"
    return {
        "key": key,
        "label": label,
        "status": status,
        "status_label": status_label,
        "tone": tone,
        "writes_packet": writes_packet,
        "message": message,
        "recovery_result_status": packet_status,
        "recovery_result_status_label": _to_text(packet_result.get("status_label"), "待验证"),
        "recovery_result_updated_at": _to_text(packet_result.get("updated_at"), "暂无"),
        "recovery_result_source": _to_text(packet_result.get("source"), "本地恢复状态"),
        "external_call_policy": "not_triggered",
        "deepseek_called": False,
    }


def attach_margin_etf_evidence_recovery_results(snapshot: Any = None) -> dict:
    payload = _as_mapping(snapshot)
    margin_summary = _as_mapping(payload.get("margin_etf_summary"))
    etf_packet = _as_mapping(payload.get("etf_packet"))
    candidates = _as_list(margin_summary.get("recommended_etfs")) or _as_list(etf_packet.get("recommended_etfs"))
    enriched = []
    for raw_candidate in candidates:
        candidate = _as_mapping(raw_candidate)
        if not candidate:
            continue
        evidence_rows = []
        counts = {"verified": 0, "review": 0, "blocked": 0, "waiting": 0}
        for raw_evidence in _as_list(candidate.get("evidence_chain")):
            evidence = _as_mapping(raw_evidence)
            if not evidence:
                continue
            result = _etf_evidence_recovery_status(evidence, payload)
            evidence["writes_packet"] = result["writes_packet"]
            evidence["recovery_result_status"] = result["status"]
            evidence["recovery_result_status_label"] = result["status_label"]
            evidence["recovery_result_tone"] = result["tone"]
            evidence["recovery_result_message"] = result["message"]
            evidence["recovery_result_updated_at"] = result["recovery_result_updated_at"]
            evidence["recovery_result_source"] = result["recovery_result_source"]
            evidence["recovery_result_external_call_policy"] = "not_triggered"
            evidence["deepseek_called"] = False
            counts[result["status"]] = counts.get(result["status"], 0) + 1
            evidence_rows.append(evidence)
        candidate["evidence_chain"] = evidence_rows
        candidate["evidence_recovery_items"] = [
            {
                "label": item["label"],
                "status": item["status"],
                "status_label": item["status_label"],
                "tone": item["tone"],
                "writes_packet": item["writes_packet"],
                "message": item["message"],
                "deepseek_called": False,
            }
            for item in (_etf_evidence_recovery_status(row, payload) for row in evidence_rows)
        ]
        candidate["evidence_recovery_summary"] = (
            f"已验证 {counts['verified']}｜需复核 {counts['review']}｜仍阻断 {counts['blocked']}｜待验证 {counts['waiting']}"
            if evidence_rows
            else "ETF 证据恢复结果待验证"
        )
        if counts["blocked"]:
            impact = {
                "status": "blocked",
                "label": "仍不可放大",
                "tone": "failed",
                "impact_text": "存在阻断证据，ETF 不能加融资、追高或扩大风险暴露。",
            }
        elif counts["waiting"] or counts["review"]:
            impact = {
                "status": "still_verify",
                "label": "仍需复核",
                "tone": "stale",
                "impact_text": "ETF 证据未完全验证，只能按观察/小仓位准备处理。",
            }
        elif counts["verified"]:
            impact = {
                "status": "verified",
                "label": "证据已验证",
                "tone": "ready",
                "impact_text": "ETF 核心证据已回流；仍需遵守不追高和融资现金缓冲。",
            }
        else:
            impact = {
                "status": "waiting",
                "label": "待验证",
                "tone": "missing",
                "impact_text": "ETF 证据恢复结果待验证。",
            }
        candidate["evidence_recovery_impact"] = {
            **impact,
            "summary": candidate["evidence_recovery_summary"],
            "external_call_policy": "not_triggered",
            "deepseek_called": False,
        }
        enriched.append(candidate)
    margin_summary["recommended_etfs"] = enriched[:MAX_CANDIDATES]
    payload["margin_etf_summary"] = margin_summary
    if etf_packet:
        etf_packet["recommended_etfs"] = enriched[:MAX_CANDIDATES]
        payload["etf_packet"] = etf_packet
    return payload


def build_legacy_migration_recovery_actions_snapshot(
    legacy_migration_map: Any = None,
    limit: int = MAX_CAPABILITY_ITEMS,
) -> list[dict]:
    migration = _as_mapping(legacy_migration_map)
    actions = []
    for raw in _as_list(migration.get("items")):
        item = _as_mapping(raw)
        if not item or item.get("is_complete") or _to_text(item.get("completion_status")) == "complete":
            continue
        progress = _as_mapping(item.get("completion_progress"))
        missing_targets = [
            _to_text(target)
            for target in _as_list(progress.get("missing_targets"))
            if _to_text(target)
        ]
        writes_packet = missing_targets[0] if missing_targets else _to_text(item.get("writes_packet"), "command_center_packet")
        legacy_tab = _to_text(item.get("legacy_tab"), "高级工具")
        label = _to_text(item.get("label"), "旧版能力")
        migration_state = _to_text(item.get("migration_state"), "wired_waiting_data")
        is_blocked = migration_state == "blocked" or _to_text(item.get("completion_status")) == "blocked"
        status = "failed" if is_blocked else "waiting"
        status_label = _to_text(item.get("completion_label") or item.get("migration_label"), "待回流")
        missing_text = _to_text(progress.get("missing_target_text") or item.get("missing_target_text"), writes_packet)
        target_text = _to_text(progress.get("target_packet_text") or item.get("target_packet_text"), writes_packet)
        progress_label = _to_text(progress.get("progress_label"), "0/0")
        reason = _to_text(
            item.get("completion_summary"),
            f"{label} 仍未完成迁移；目标 packet 待回流。",
        )
        actions.append(
            {
                "key": f"legacy_migration:{_to_text(item.get('key'), label)}:{writes_packet}",
                "label": label,
                "source_type": "legacy_migration",
                "source_label": "旧版迁移地图",
                "status": status,
                "status_label": status_label,
                "tone": _to_text(item.get("tone"), "failed" if is_blocked else "missing"),
                "priority": 1 if is_blocked else 3,
                "reason": f"{reason} 迁移进度 {progress_label}；待处理 {missing_text}。",
                "diagnostic_answer": _to_text(
                    item.get("current_blocker"),
                    f"{label} 仍需要从旧工具箱手动回流 {missing_text}。",
                ),
                "interface_diagnostic_answer": _to_text(
                    item.get("current_blocker"),
                    f"{label} 仍需要从旧工具箱手动回流 {missing_text}。",
                ),
                "decision_guardrail": f"{label} 未完成迁移前，相关证据只能标记为待验证，不能单独作为交易依据。",
                "action_label": _to_text(item.get("action_label"), f"打开{legacy_tab}"),
                "toolbox_entry": _to_text(item.get("toolbox_entry"), f"高级工具箱 / {legacy_tab}"),
                "workspace_target": _to_text(item.get("workspace_target"), "高级工具箱（旧版保留）"),
                "workspace_state_key": _to_text(item.get("workspace_state_key"), "workspace_mode_v2"),
                "legacy_tab_state_key": _to_text(item.get("legacy_tab_state_key"), "legacy_workspace_selected_tab"),
                "legacy_tab": legacy_tab,
                "navigation_label": f"主导航切到高级工具箱（旧版保留）→ 高级工具模块选择{legacy_tab}；手动执行后回流 {writes_packet}。",
                "writes_packet": writes_packet,
                "target_packet_text": target_text,
                "missing_target_text": missing_text,
                "completion_progress_label": progress_label,
                "refresh_policy": "button_gated",
                "recovery_button_context": (
                    f"这里只打开旧版“{legacy_tab}”入口；对应检测仍需手动点击，结果回流 {writes_packet}。"
                    "不会自动调用 DeepSeek、回测、全市场扫描或重型数据接口。"
                ),
                "external_call_policy": "not_triggered",
                "deepseek_called": False,
            }
        )
    actions = sorted(actions, key=lambda action: (action["priority"], action["label"], action["writes_packet"]))
    return actions[: max(1, int(limit or MAX_CAPABILITY_ITEMS))]


def build_old_workspace_packet_bridge(snapshot: Any = None, limit: int = MAX_CAPABILITY_ITEMS) -> dict:
    payload = _as_mapping(snapshot)
    migration = _as_mapping(payload.get("legacy_migration_map"))
    migration_items = [_as_mapping(item) for item in _as_list(migration.get("items")) if _as_mapping(item)]
    bridge_items = []
    counts = {"recovered": 0, "cached": 0, "blocked": 0, "waiting": 0}
    for item in migration_items:
        progress = _as_mapping(item.get("completion_progress"))
        missing_targets = [_to_text(target) for target in _as_list(progress.get("missing_targets")) if _to_text(target)]
        target_packets = [_to_text(target) for target in _as_list(item.get("command_center_packets")) if _to_text(target)]
        writes_packet = _to_text(item.get("writes_packet") or (missing_targets[0] if missing_targets else ""), "")
        if not writes_packet and target_packets:
            writes_packet = target_packets[0]
        packet_key, packet = _resolve_recovery_packet(payload, writes_packet)
        fallback_status = _to_text(item.get("completion_status") or item.get("migration_state"))
        display_state = _recovery_display_state(packet, writes_packet, fallback_status=fallback_status)
        bridge_status = display_state["status"]
        if bridge_status not in counts:
            bridge_status = "waiting"
        counts[bridge_status] += 1
        label = _to_text(item.get("label"), "旧版能力")
        manual_action = _as_mapping(item.get("manual_action"))
        legacy_tab = _to_text(item.get("legacy_tab") or manual_action.get("legacy_tab"), label)
        if bridge_status in {"blocked", "waiting"}:
            decision_guardrail = f"{label} 未回流为可读 packet 前，只能标记为待验证，不能作为加仓、追高或加融资依据。"
        elif bridge_status == "cached":
            decision_guardrail = f"{label} 当前使用缓存；执行前需要复核日期、来源和覆盖口径。"
        else:
            decision_guardrail = f"{label} 已回流为综合中心 packet；仍需和价格、纪律、仓位规则共同复核。"
        bridge_items.append(
            {
                "key": _to_text(item.get("key"), label),
                "label": label,
                "legacy_tab": legacy_tab,
                "home_surface": _to_text(item.get("home_surface"), "综合推演中心"),
                "target_packet_text": _to_text(item.get("target_packet_text") or progress.get("target_packet_text"), writes_packet),
                "missing_target_text": _to_text(item.get("missing_target_text") or progress.get("missing_target_text"), "无"),
                "writes_packet": writes_packet,
                "packet_key": packet_key,
                "bridge_status": bridge_status,
                "bridge_label": display_state["label"],
                "tone": display_state["tone"],
                "completion_label": _to_text(item.get("completion_label"), display_state["label"]),
                "completion_progress_label": _to_text(progress.get("progress_label"), "0/0"),
                "action_label": _to_text(item.get("action_label") or manual_action.get("action_label"), f"打开{legacy_tab}"),
                "toolbox_entry": _to_text(item.get("toolbox_entry") or manual_action.get("toolbox_entry"), f"高级工具箱 / {legacy_tab}"),
                "navigation_label": _to_text(
                    item.get("navigation_label") or manual_action.get("navigation_label"),
                    f"主导航切到高级工具箱（旧版保留）→ 高级工具模块选择{legacy_tab}；手动执行后回流 {writes_packet}。",
                ),
                "decision_guardrail": decision_guardrail,
                "refresh_policy": "button_gated",
                "external_call_policy": "not_triggered",
                "deepseek_called": False,
            }
        )
    bridge_items = sorted(
        bridge_items,
        key=lambda row: (
            {"blocked": 0, "waiting": 1, "cached": 2, "recovered": 3}.get(row["bridge_status"], 4),
            row["label"],
        ),
    )[: max(1, int(limit or MAX_CAPABILITY_ITEMS))]
    if counts["blocked"]:
        status = "blocked"
        tone = "failed"
        headline = f"旧能力有 {counts['blocked']} 项仍阻断 packet 回流"
    elif counts["waiting"] or counts["cached"]:
        status = "partial"
        tone = "stale"
        headline = f"旧能力待回流/缓存复核 {counts['waiting'] + counts['cached']} 项"
    elif counts["recovered"]:
        status = "ready"
        tone = "ready"
        headline = "旧能力已回流为综合中心 packet"
    else:
        status = "missing"
        tone = "missing"
        headline = "旧能力 packet 桥待生成"
    next_action = (
        f"优先处理 {bridge_items[0]['label']}：{bridge_items[0]['action_label']}，回流 {bridge_items[0]['writes_packet']}。"
        if bridge_items and bridge_items[0]["bridge_status"] != "recovered"
        else "继续以综合推演中心为主入口；旧工具只作为手动恢复入口。"
    )
    return {
        "title": "旧工具能力 → 综合中心 packet 桥",
        "status": status,
        "tone": tone,
        "headline": headline,
        "summary": f"已回流 {counts['recovered']}｜使用缓存 {counts['cached']}｜仍阻断 {counts['blocked']}｜待回流 {counts['waiting']}",
        "items": bridge_items,
        "next_action": next_action,
        "safe_mode_text": "这里只读取旧版迁移地图、本地 packet 和恢复状态；不会自动调用 DeepSeek、回测、全市场扫描或重型数据接口。",
        "external_call_policy": "not_triggered",
        "deepseek_called": False,
    }


def build_home_data_recovery_center(snapshot: Any = None, limit: int = MAX_CAPABILITY_ITEMS) -> dict:
    payload = _as_mapping(snapshot)
    data_actions = _as_list(payload.get("data_recovery_actions"))
    timeline_actions = _as_list(
        payload.get("command_center_data_health_timeline_recovery_actions")
        or payload.get("data_health_timeline_recovery_actions")
    )
    legacy_fact_actions = _as_list(payload.get("legacy_a_share_fact_recovery_actions"))
    a_share_actions = _as_list(_as_mapping(payload.get("a_share_user_data_diagnostic")).get("recovery_actions"))
    legacy_migration_actions = build_legacy_migration_recovery_actions_snapshot(
        payload.get("legacy_migration_map"),
        limit=limit,
    )
    tool_actions = _as_list(payload.get("tool_recovery_actions"))
    action_sources = [
        ("data_source", "数据源能力", data_actions, 1),
        ("data_health_timeline", "接口健康时间线", timeline_actions, 1),
        ("a_share_fact", "旧版 A股事实卡", legacy_fact_actions, 2),
        ("a_share", "A股数据能力", a_share_actions, 3),
        ("legacy_migration", "旧版迁移地图", legacy_migration_actions, 3),
        ("legacy_tool", "旧工具能力", tool_actions, 3),
        ("next_ticket_evidence", "下一票候选证据", _as_list(payload.get("next_ticket_evidence_recovery_actions")), 2),
    ]
    recovery_result_lookup = _recovery_result_lookup_from_state(payload)
    seen = set()
    actions = []
    groups = []
    for source_type, source_label, source_actions, default_priority in action_sources:
        group_items = []
        for raw in source_actions:
            item = _normalize_recovery_center_action(raw, source_type, source_label, default_priority)
            if not item or item.get("refresh_policy") == "not_needed":
                continue
            item = attach_recovery_result_status_to_action(item, payload, recovery_result_lookup)
            dedupe_key = item.get("writes_packet") or f"{source_type}:{item.get('key')}"
            if source_type == "next_ticket_evidence":
                dedupe_key = f"{source_type}:{dedupe_key}"
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            group_items.append(item)
            actions.append(item)
        groups.append(
            {
                "key": source_type,
                "label": source_label,
                "count": len(group_items),
                "items": group_items,
            }
        )
    actions = sorted(actions, key=lambda item: (item["priority"], item["source_label"], item["label"]))
    actions = actions[: max(1, int(limit or MAX_CAPABILITY_ITEMS))]
    priority_lanes = build_recovery_priority_lanes(actions)
    decision_priority_queue = build_decision_priority_queue(actions)
    if not actions:
        tone = "ready"
        headline = "恢复队列为空"
        summary = "当前没有需要恢复的数据源、A股诊断项或旧工具 packet。"
        next_action = "继续查看交易快照；如需更新，使用刷新今日基础数据按钮。"
    else:
        has_blocker = any(str(item.get("status") or "") in {"permission_denied", "failed", "error"} for item in actions)
        tone = "failed" if has_blocker else "stale"
        headline = f"待恢复 {len(actions)} 项数据/工具能力"
        first = actions[0]
        summary = f"优先处理 {first['label']}：{first['action_label']}，回流 {first['writes_packet']}。"
        next_action = "按队列手动恢复；页面打开不会自动请求 DeepSeek、回测、全市场扫描或批量数据接口。"
    return {
        "title": "数据恢复中心",
        "tone": tone,
        "headline": headline,
        "summary": summary,
        "next_action": next_action,
        "actions": actions,
        "groups": groups,
        "priority_lanes": priority_lanes,
        "decision_priority_queue": decision_priority_queue,
        "decision_priority_summary": (
            f"先处理 {decision_priority_queue[0]['priority_label']}：{decision_priority_queue[0]['label']}。"
            if decision_priority_queue
            else "暂无阻断交易判断的数据恢复项。"
        ),
        "action_count": len(actions),
        "safe_mode_text": "这里只整理恢复队列；所有数据请求仍由按钮触发，DeepSeek 不参与恢复动作。",
        "deepseek_called": False,
    }


def build_tool_recovery_navigation_state(action: Any = None) -> dict:
    item = _as_mapping(action)
    workspace_state_key = _to_text(item.get("workspace_state_key"), "workspace_mode_v2")
    legacy_tab_state_key = _to_text(item.get("legacy_tab_state_key"), "legacy_workspace_selected_tab")
    workspace_target = _to_text(item.get("workspace_target"), "高级工具箱（旧版保留）")
    legacy_tab = _to_text(item.get("legacy_tab"))
    if not legacy_tab:
        return {}
    return {
        workspace_state_key: workspace_target,
        legacy_tab_state_key: legacy_tab,
        "command_center_last_tool_recovery_key": _to_text(item.get("key")),
        "command_center_last_tool_recovery_label": _to_text(item.get("label"), legacy_tab),
        "command_center_last_tool_recovery_writes_packet": _to_text(item.get("writes_packet")),
        "command_center_last_tool_recovery_target_tab": legacy_tab,
        "command_center_last_tool_recovery_policy": "navigation_only",
    }


def build_tool_recovery_context_notice(state: Any = None, selected_tab: Any = "") -> dict:
    state_map = _as_mapping(state)
    if _to_text(state_map.get("command_center_last_tool_recovery_policy")) != "navigation_only":
        return {}
    label = _to_text(state_map.get("command_center_last_tool_recovery_label"), "旧工具能力")
    writes_packet = _to_text(state_map.get("command_center_last_tool_recovery_writes_packet"), "command_center_packet")
    selected = _to_text(selected_tab, _to_text(state_map.get("legacy_workspace_selected_tab"), "高级工具"))
    target_tab = _to_text(
        state_map.get("command_center_last_tool_recovery_target_tab"),
        _to_text(state_map.get("legacy_workspace_selected_tab"), selected),
    )
    is_target_tab = selected == target_tab
    if is_target_tab:
        message = f"你是从首页恢复队列进入“{target_tab}”；请在本模块手动点击对应按钮恢复 {writes_packet}。"
        action_hint = "这里只是导航提示，不会自动运行扫描、回测、DeepSeek 或重型数据接口。"
    else:
        message = f"首页恢复队列目标是“{target_tab}”，当前在“{selected}”；请先切回“{target_tab}”再恢复 {writes_packet}。"
        action_hint = "当前模块不会显示该恢复按钮；这仍然只是导航提示，不会自动运行任何重型任务。"
    return {
        "status": "ready",
        "title": "来自首页恢复队列",
        "label": label,
        "selected_tab": selected,
        "target_tab": target_tab,
        "is_target_tab": is_target_tab,
        "writes_packet": writes_packet,
        "message": message,
        "action_hint": action_hint,
        "safety_text": "恢复成功后的结构化结果会回流到 Home Action Snapshot。",
        "deepseek_called": False,
        "external_call_policy": "not_triggered",
    }


TOOL_RECOVERY_MANUAL_CHECKS = {
    "command_center_moneyflow_packet": {
        "check_key": "moneyflow",
        "label": "个股资金流",
        "button_label": "手动检测个股资金流",
        "status_label": "正在手动检测个股资金流...",
        "result_label": "资金流",
    },
    "command_center_dragon_tiger_packet": {
        "check_key": "dragon_tiger",
        "label": "龙虎榜",
        "button_label": "手动检测龙虎榜",
        "status_label": "正在手动检测龙虎榜...",
        "result_label": "龙虎榜",
    },
    "command_center_margin_packet": {
        "check_key": "margin",
        "label": "融资融券",
        "button_label": "手动检测融资融券",
        "status_label": "正在手动检测融资融券权限...",
        "result_label": "融资融券",
    },
    "command_center_limit_emotion_packet": {
        "check_key": "limit_emotion",
        "label": "涨跌停/情绪",
        "button_label": "手动检测涨跌停/情绪",
        "status_label": "正在手动检测涨跌停/情绪权限...",
        "result_label": "涨跌停/情绪",
    },
    "command_center_chip_packet": {
        "check_key": "chip_radar",
        "label": "筹码/胜率",
        "button_label": "手动检测筹码/胜率",
        "status_label": "正在手动检测筹码/胜率...",
        "result_label": "筹码/胜率",
    },
    "command_center_hard_risk_packet": {
        "check_key": "hard_risk",
        "label": "公告/硬风险",
        "button_label": "手动检测公告/硬风险",
        "status_label": "正在手动检测公告/硬风险...",
        "result_label": "公告/硬风险",
    },
}


def build_tool_recovery_manual_check_hint(state: Any = None, selected_tab: Any = "") -> dict:
    context = build_tool_recovery_context_notice(state, selected_tab=selected_tab)
    if not context:
        return {}
    if not context.get("is_target_tab", True):
        return {
            "available": False,
            "label": context["label"],
            "selected_tab": context["selected_tab"],
            "target_tab": context["target_tab"],
            "writes_packet": context["writes_packet"],
            "message": f"当前在“{context['selected_tab']}”；请先切回“{context['target_tab']}”再手动恢复 {context['writes_packet']}。",
            "external_call_policy": "not_triggered",
            "deepseek_called": False,
        }
    writes_packet = context["writes_packet"]
    config = TOOL_RECOVERY_MANUAL_CHECKS.get(writes_packet)
    if not config:
        return {
            "available": False,
            "label": context["label"],
            "selected_tab": context["selected_tab"],
            "writes_packet": writes_packet,
            "message": f"{writes_packet} 还没有绑定单项检测按钮；请在当前高级工具模块手动查找对应刷新入口。",
            "external_call_policy": "not_triggered",
            "deepseek_called": False,
        }
    return {
        "available": True,
        "label": config["label"],
        "selected_tab": context["selected_tab"],
        "writes_packet": writes_packet,
        "check_key": config["check_key"],
        "button_label": config["button_label"],
        "status_label": config["status_label"],
        "result_label": config["result_label"],
        "help_text": f"只检测 {config['label']} 并回流 {writes_packet}；不自动运行 DeepSeek、回测、全市场扫描或批量刷新。",
        "external_call_policy": "button_gated",
        "deepseek_called": False,
    }


def _tool_packet_has_payload(packet: Mapping[str, Any], writes_packet: str = "") -> bool:
    if not packet:
        return False
    status = _to_text(packet.get("status")).lower()
    data_status = _to_text(packet.get("data_status") or packet.get("cache_state")).lower()
    if status in {"ready", "completed", "ok", "success"} or data_status in {"ready", "cached"}:
        return True
    payload_keys = {
        "command_center_radar_packet": ("top_candidates", "display_count", "total_count"),
        "command_center_etf_packet": ("recommended_etfs", "today_main_direction"),
        "command_center_discipline_packet": ("metric_items", "evidence_items", "backtest_status"),
        "command_center_quant_packet": ("score", "evidence_items", "summary"),
    }.get(writes_packet, ("summary", "items", "updated_at"))
    for key in payload_keys:
        value = packet.get(key)
        if isinstance(value, (list, tuple)) and value:
            return True
        if isinstance(value, Mapping) and value:
            return True
        if _to_text(value):
            return True
    return False


def _tool_packet_recovery_state(packet: Mapping[str, Any], writes_packet: str = "") -> str:
    if not packet:
        return "waiting"
    status = _to_text(packet.get("status")).lower()
    data_status = _to_text(packet.get("data_status") or packet.get("cache_state")).lower()
    blocked_states = {
        "failed",
        "error",
        "failure",
        "permission_denied",
        "disabled_this_session",
        "network_failed",
        "not_configured",
        "权限不足",
        "本会话跳过",
        "失败",
    }
    ready_states = {"ready", "completed", "ok", "success", "available", "cached", "using_cache", "今日已刷新", "使用缓存"}
    if status in blocked_states or data_status in blocked_states:
        return "blocked"
    if status in ready_states or data_status in ready_states:
        return "recovered"
    if _tool_packet_has_payload(packet, writes_packet):
        return "recovered"
    return "waiting"


def _resolve_recovery_packet(container: Any = None, writes_packet: str = "") -> tuple[str, dict]:
    payload = _as_mapping(container)
    direct_packet = _as_mapping(payload.get(writes_packet))
    if direct_packet:
        return writes_packet, direct_packet
    snapshot_key = RECOVERY_WRITES_PACKET_TO_SNAPSHOT_KEY.get(_to_text(writes_packet), "")
    snapshot_packet = _as_mapping(payload.get(snapshot_key))
    if snapshot_packet:
        return snapshot_key, snapshot_packet
    return snapshot_key or writes_packet, {}


def _recovery_display_state(packet: Mapping[str, Any], writes_packet: str = "", fallback_status: str = "") -> dict:
    packet_state = _tool_packet_recovery_state(packet, writes_packet)
    status = _to_text(packet.get("status")).lower()
    data_status = _to_text(packet.get("data_status") or packet.get("cache_state")).lower()
    status_label = _to_text(packet.get("status_label") or packet.get("label"))
    fallback = _to_text(fallback_status).lower()
    if packet_state == "blocked" or fallback == "blocked":
        label = "权限不足" if ("permission" in data_status or "权限" in status_label) else "仍失败"
        return {"status": "blocked", "label": label, "tone": "failed"}
    if packet_state == "recovered":
        if data_status in {"cached", "using_cache", "stale_cache"} or status in {"cached", "using_cache"}:
            return {"status": "cached", "label": "使用缓存", "tone": "stale"}
        return {"status": "recovered", "label": "已回流", "tone": "ready"}
    if fallback == "recovered":
        return {"status": "waiting", "label": "待验证", "tone": "stale"}
    if fallback == "waiting":
        return {"status": "waiting", "label": "待验证", "tone": "stale"}
    return {"status": "waiting", "label": "待验证", "tone": "missing"}


def build_recovery_result_status_strip(
    state: Any = None,
    latest_notice: Any = None,
    data_recovery_center: Any = None,
) -> dict:
    """Summarize whether the latest manual recovery actually wrote a usable packet."""
    state_map = _as_mapping(state)
    notice = _as_mapping(latest_notice) or _as_mapping(state_map.get("latest_recovery_result_notice"))
    if not notice:
        notice = build_latest_recovery_result_notice(
            state_map,
            selected_tab=state_map.get("legacy_workspace_selected_tab"),
        )
    center = _as_mapping(data_recovery_center) or _as_mapping(state_map.get("data_recovery_center"))
    if not notice:
        first_queue_item = {}
        for item in _as_list(center.get("decision_priority_queue")) or _as_list(center.get("actions")):
            if isinstance(item, Mapping):
                first_queue_item = dict(item)
                break
        queue_hint = _to_text(first_queue_item.get("label"), "暂无恢复记录")
        return {
            "title": "最近恢复状态",
            "status": "waiting",
            "tone": "missing",
            "headline": "尚未运行恢复",
            "summary": f"还没有旧工具或数据诊断结果回流；优先项：{queue_hint}。",
            "items": [],
            "next_action": "按决策优先队列手动恢复；页面打开不会自动请求外部接口。",
            "deepseek_called": False,
            "external_call_policy": "not_triggered",
        }

    writes_packet = _to_text(notice.get("writes_packet"), "command_center_packet")
    packet_key, packet = _resolve_recovery_packet(state_map, writes_packet)
    display_state = _recovery_display_state(packet, writes_packet, fallback_status=notice.get("status"))
    updated_at = _to_text(
        packet.get("updated_at")
        or packet.get("generated_at")
        or packet.get("checked_at")
        or notice.get("updated_at"),
        "暂无",
    )
    source = _to_text(packet.get("source") or notice.get("source"), "本地恢复状态")
    label = _to_text(notice.get("label"), "恢复项")
    status_label = display_state["label"]
    if display_state["status"] == "recovered":
        headline = "恢复结果已回流"
        summary = f"{label} 已回流到 {writes_packet}；综合中心可以读取这项结构化结果。"
    elif display_state["status"] == "cached":
        headline = "恢复结果使用缓存"
        summary = f"{label} 目前读取到缓存结果；执行前仍需复核日期、来源和覆盖口径。"
    elif display_state["status"] == "blocked":
        headline = "恢复结果仍失败"
        summary = f"{label} 仍未形成可用回流；不能把缺失数据当成安全信号。"
    else:
        headline = "恢复结果待验证"
        summary = f"{label} 尚未检测到可读回流；需要在对应旧工具里手动运行按钮。"
    item = {
        "label": label,
        "writes_packet": writes_packet,
        "packet_key": packet_key,
        "status": display_state["status"],
        "status_label": status_label,
        "tone": display_state["tone"],
        "message": _to_text(notice.get("message"), summary),
        "updated_at": updated_at,
        "source": source,
        "next_action": _to_text(notice.get("next_action"), "返回综合推演中心查看快照。"),
        "deepseek_called": False,
        "external_call_policy": _to_text(notice.get("external_call_policy"), "not_triggered"),
    }
    return {
        "title": "最近恢复状态",
        "status": display_state["status"],
        "tone": display_state["tone"],
        "headline": headline,
        "summary": summary,
        "items": [item],
        "next_action": item["next_action"],
        "deepseek_called": False,
        "external_call_policy": item["external_call_policy"],
    }


def _recovery_timeline_event_type(status: Any = "") -> str:
    text = _to_text(status)
    if text == "recovered":
        return "packet_recovered"
    if text == "cached":
        return "packet_cached"
    if text == "blocked":
        return "packet_blocked"
    return "packet_waiting"


def _recovery_timeline_item(raw: Any = None, source_type: Any = "") -> dict:
    item = _as_mapping(raw)
    if not item:
        return {}
    status = _to_text(item.get("status"), "waiting")
    label = _to_text(item.get("label"), "恢复项")
    writes_packet = _to_text(item.get("writes_packet"), "command_center_packet")
    updated_at = _to_text(item.get("updated_at"), "暂无")
    packet_key = _to_text(item.get("packet_key"), writes_packet)
    source = _to_text(item.get("source"), "本地恢复状态")
    event_type = _recovery_timeline_event_type(status)
    return {
        "key": _to_text(
            item.get("key"),
            f"{event_type}:{writes_packet}:{updated_at}:{label}",
        ),
        "event_type": event_type,
        "source_type": _to_text(item.get("source_type"), _to_text(source_type, "recovery_result")),
        "label": label,
        "writes_packet": writes_packet,
        "packet_key": packet_key,
        "status": status,
        "status_label": _to_text(item.get("status_label"), "待验证"),
        "tone": _to_text(item.get("tone"), {"recovered": "ready", "cached": "stale", "blocked": "failed"}.get(status, "missing")),
        "message": _to_text(item.get("message"), f"{label} 恢复结果待验证。"),
        "updated_at": updated_at,
        "source": source,
        "next_action": _to_text(item.get("next_action"), "返回综合推演中心查看快照。"),
        "external_call_policy": _to_text(item.get("external_call_policy"), "not_triggered"),
        "deepseek_called": False,
    }


def build_recovery_result_timeline(
    state: Any = None,
    latest_notice: Any = None,
    status_strip: Any = None,
    limit: int = 4,
) -> dict:
    """Build a read-only timeline of manual recovery outcomes for the home snapshot."""
    state_map = _as_mapping(state)
    latest = _as_mapping(latest_notice) or _as_mapping(state_map.get("latest_recovery_result_notice"))
    strip = _as_mapping(status_strip) or _as_mapping(state_map.get("recovery_result_status_strip"))
    if not strip:
        strip = build_recovery_result_status_strip(state_map, latest_notice=latest)

    timeline_source = (
        _as_mapping(state_map.get("command_center_recovery_result_timeline"))
        or _as_mapping(state_map.get("recovery_result_timeline"))
    )
    candidates = []
    for raw in _as_list(strip.get("items")):
        item = _recovery_timeline_item(raw, source_type=latest.get("source_type") or "latest_recovery_result")
        if item:
            candidates.append(item)
    if latest and not candidates:
        candidates.append(_recovery_timeline_item(latest, source_type=latest.get("source_type") or "latest_recovery_result"))
    for raw in _as_list(timeline_source.get("items")):
        item = _recovery_timeline_item(raw, source_type=raw.get("source_type") if isinstance(raw, Mapping) else "persisted_snapshot")
        if item:
            candidates.append(item)

    seen = set()
    items = []
    for item in candidates:
        key = item["key"]
        if key in seen:
            continue
        seen.add(key)
        items.append(item)
        if len(items) >= max(1, int(limit or 4)):
            break

    if items:
        status = items[0]["status"]
        tone = items[0]["tone"]
        headline = {
            "recovered": "最近恢复已回流",
            "cached": "最近恢复使用缓存",
            "blocked": "最近恢复仍受限",
        }.get(status, "最近恢复待验证")
        summary = f"最近 {len(items)} 条恢复记录；最新项：{items[0]['label']}｜{items[0]['status_label']}。"
        next_action = items[0]["next_action"]
    else:
        status = "waiting"
        tone = "missing"
        headline = "暂无恢复结果时间线"
        summary = "还没有手动恢复结果回流；按数据恢复队列进入高级工具箱后再手动检测。"
        next_action = "先处理决策优先恢复队列；页面打开不会自动请求外部接口。"

    status_counts = {
        "recovered": len([item for item in items if item["status"] == "recovered"]),
        "cached": len([item for item in items if item["status"] == "cached"]),
        "blocked": len([item for item in items if item["status"] == "blocked"]),
        "waiting": len([item for item in items if item["status"] == "waiting"]),
    }
    return {
        "title": "恢复结果时间线",
        "status": status,
        "tone": tone,
        "headline": headline,
        "summary": summary,
        "items": items,
        "status_counts": status_counts,
        "next_action": next_action,
        "external_call_policy": "not_triggered",
        "deepseek_called": False,
    }


def build_tool_recovery_result_notice(state: Any = None, selected_tab: Any = "") -> dict:
    context = build_tool_recovery_context_notice(state, selected_tab=selected_tab)
    if not context:
        return {}
    if not context.get("is_target_tab", True):
        return {
            "status": "waiting",
            "title": "恢复入口不在当前模块",
            "label": context["label"],
            "selected_tab": context["selected_tab"],
            "target_tab": context["target_tab"],
            "writes_packet": context["writes_packet"],
            "message": f"当前在“{context['selected_tab']}”，首页恢复队列目标是“{context['target_tab']}”。",
            "next_action": f"请切回“{context['target_tab']}”后手动运行对应按钮；不会自动执行旧工具。",
            "updated_at": "",
            "source": "首页恢复队列",
            "deepseek_called": False,
            "external_call_policy": "not_triggered",
        }
    state_map = _as_mapping(state)
    writes_packet = context["writes_packet"]
    packet = _as_mapping(state_map.get(writes_packet))
    recovery_state = _tool_packet_recovery_state(packet, writes_packet)
    updated_at = _to_text(packet.get("updated_at") or packet.get("generated_at") or packet.get("checked_at"))
    source = _to_text(packet.get("source"), context["selected_tab"])
    if recovery_state == "recovered":
        status = "recovered"
        title = "恢复结果已回流"
        message = f"{context['label']} 已写入 {writes_packet}；首页快照会读取该结构化结果。"
        next_action = "返回综合推演中心 2.0 后查看 Home Action Snapshot。"
    elif recovery_state == "blocked":
        status = "blocked"
        title = "恢复结果仍受限"
        reason = _to_text(packet.get("risk_note") or packet.get("message") or packet.get("summary"), "接口权限、积分、网络或交易日状态仍待处理。")
        message = f"{context['label']} 仍未形成可用回流：{reason}"
        next_action = "先检查权限/积分/交易日/网络；不要把缺失数据当作利好或安全信号。"
    else:
        status = "waiting"
        title = "恢复结果待验证"
        message = f"尚未检测到 {writes_packet} 的可读结果；请在“{context['selected_tab']}”中手动运行对应按钮。"
        next_action = "运行完成后不要刷新外部重接口，先确认本模块是否显示缓存/已刷新状态。"
    return {
        "status": status,
        "title": title,
        "label": context["label"],
        "selected_tab": context["selected_tab"],
        "writes_packet": writes_packet,
        "message": message,
        "next_action": next_action,
        "updated_at": updated_at,
        "source": source,
        "deepseek_called": False,
        "external_call_policy": "not_triggered",
    }


def build_a_share_diagnostic_recovery_result_notice(state: Any = None) -> dict:
    state_map = _as_mapping(state)
    result = _as_mapping(state_map.get("command_center_last_a_share_diagnostic_recovery_result"))
    if not result:
        return {}
    label = _to_text(result.get("label"), "A股数据")
    writes_packet = _to_text(result.get("writes_packet"), "command_center_facts_packet")
    legacy_gap_diagnostic = _legacy_gap_diagnostic_for_writes_packet(writes_packet, label)
    capability_state = _to_text(result.get("capability_state") or result.get("state"), "unknown")
    status_label = _to_text(result.get("status_label") or result.get("status"), "待验证")
    message = _to_text(result.get("message") or result.get("action_hint") or result.get("error"), "已完成手动检测。")
    updated_at = _to_text(result.get("checked_at") or result.get("updated_at"))
    packet = _as_mapping(state_map.get(writes_packet))
    has_packet_payload = _tool_packet_has_payload(packet, writes_packet)
    if capability_state == "available" or has_packet_payload:
        status = "recovered"
        tone = "ready"
        title = "A股数据恢复结果已回流"
        next_action = "继续查看 Home Action Snapshot；执行前仍需复核日期、来源和仓位纪律。"
    elif capability_state in {"permission_denied", "disabled_this_session", "not_configured", "network_failed", "failed"}:
        status = "blocked"
        tone = "failed"
        title = "A股数据恢复仍受限"
        next_action = "保持安全空态或缓存观察；权限、网络或配置恢复后再手动检测。"
    else:
        status = "waiting"
        tone = "stale"
        title = "A股数据恢复待验证"
        next_action = "等待交易日数据发布或稍后再次手动检测；不要把缺失数据当成无风险。"
    return {
        "status": status,
        "tone": tone,
        "title": title,
        "label": label,
        "capability_state": capability_state,
        "status_label": status_label,
        "message": f"{label}：{status_label}｜{message}",
        "next_action": next_action,
        "writes_packet": writes_packet,
        "updated_at": updated_at,
        "source": _to_text(result.get("source") or result.get("api_hint"), "A股手动检测"),
        "why_not_found": _to_text(legacy_gap_diagnostic.get("why_not_found")),
        "button_context": _to_text(legacy_gap_diagnostic.get("button_context")),
        "decision_guardrail": _to_text(legacy_gap_diagnostic.get("decision_guardrail")),
        "manual_recovery_steps": _as_list(legacy_gap_diagnostic.get("manual_recovery_steps")),
        "deepseek_called": False,
        "external_call_policy": "button_gated",
    }


def _with_recovery_notice_source(notice: Mapping[str, Any], source_type: str) -> dict:
    payload = dict(notice)
    payload["source_type"] = source_type
    payload.setdefault("tone", {
        "recovered": "ready",
        "blocked": "failed",
        "waiting": "stale",
    }.get(_to_text(payload.get("status")), "missing"))
    payload.setdefault("deepseek_called", False)
    payload.setdefault("external_call_policy", "not_triggered")
    return payload


def build_latest_recovery_result_notice(state: Any = None, selected_tab: Any = "") -> dict:
    state_map = _as_mapping(state)
    preferred_source = _to_text(state_map.get("command_center_last_recovery_result_source"))
    if preferred_source == "tool_recovery":
        tool_notice = build_tool_recovery_result_notice(state, selected_tab=selected_tab)
        if tool_notice:
            return _with_recovery_notice_source(tool_notice, "tool_recovery")
        diagnostic_notice = build_a_share_diagnostic_recovery_result_notice(state)
        if diagnostic_notice:
            return _with_recovery_notice_source(diagnostic_notice, "a_share_diagnostic")
        return {}
    diagnostic_notice = build_a_share_diagnostic_recovery_result_notice(state)
    if diagnostic_notice:
        return _with_recovery_notice_source(diagnostic_notice, "a_share_diagnostic")
    tool_notice = build_tool_recovery_result_notice(state, selected_tab=selected_tab)
    if tool_notice:
        return _with_recovery_notice_source(tool_notice, "tool_recovery")
    return {}


def resolve_data_capability_packet(state: Any = None) -> dict:
    state_map = _as_mapping(state)
    healthcheck = _as_mapping(state_map.get("last_data_source_healthcheck"))
    command_packet = _as_mapping(state_map.get("command_center_data_capability_packet"))
    a_share_packet = _as_mapping(state_map.get("a_share_professional_data_capability"))
    professional_facts = _as_mapping(state_map.get("a_share_professional_facts"))
    facts_capability = _as_mapping(professional_facts.get("data_capability"))
    health_data_capability = _as_mapping(healthcheck.get("data_capability"))
    if health_data_capability and not a_share_packet:
        return health_data_capability
    if a_share_packet or healthcheck:
        unified = data_capability_service.build_unified_provider_capability_packet(
            health_result=healthcheck,
            a_share_packet=a_share_packet or facts_capability,
            include_manual_providers=bool(healthcheck or a_share_packet or facts_capability or command_packet),
        )
        if unified.get("items"):
            return unified
    for explicit in (
        command_packet,
        health_data_capability,
        facts_capability,
        _as_mapping(healthcheck.get("tushare")),
    ):
        if explicit:
            return explicit
    if professional_facts:
        return data_capability_service.build_a_share_professional_capability_packet(
            professional_facts,
            checked_at=professional_facts.get("updated_at") or "",
        )
    return {}


def build_holding_action(target: str = "", position_profile: Any = None, strategy_packet: Any = None, state: Any = None) -> dict:
    state_map = _as_mapping(state)
    profile = _as_mapping(position_profile) or _as_mapping(state_map.get("position_profile")) or _as_mapping(state_map.get("current_holding_context"))
    strategy = _as_mapping(strategy_packet)
    ticker = _to_text(profile.get("ticker") or profile.get("current_holding_ticker") or target)
    pnl_pct = _to_number(profile.get("pnl_pct") or profile.get("floating_profit_pct"))
    pnl_amount = _to_number(profile.get("pnl_amount") or profile.get("floating_profit_amount"))
    pnl_text = _to_text(profile.get("profit_state"))
    if not pnl_text:
        if pnl_pct is not None and pnl_amount is not None:
            pnl_text = f"{pnl_pct:+.2f}% / ¥{pnl_amount:,.0f}"
        elif pnl_pct is not None:
            pnl_text = f"{pnl_pct:+.2f}%"
        else:
            pnl_text = "暂无"
    return {
        "ticker": ticker,
        "name": _to_text(profile.get("name") or profile.get("current_holding_name")),
        "investment_horizon": _to_text(
            profile.get("investment_horizon")
            or profile.get("holding_period")
            or profile.get("trade_horizon")
            or state_map.get("investment_horizon")
            or state_map.get("holding_period")
        ),
        "cost": _to_number(profile.get("cost_price") or profile.get("cost")),
        "shares": _to_number(profile.get("holding_units") or profile.get("shares")),
        "current_price": _to_number(profile.get("current_price")),
        "floating_pnl": {"pct": pnl_pct, "amount": pnl_amount},
        "floating_pnl_text": pnl_text,
        "action_state": _to_text(strategy.get("action") or profile.get("holding_action_state") or profile.get("normalized_position_state"), "待刷新"),
        "add_condition": _to_text(strategy.get("add_condition"), "等待量化、纪律和市场至少两项同向后再考虑。"),
        "reduce_condition": _to_text(strategy.get("reduce_condition"), "触发止损、减仓或风险预算失效时优先降低暴露。"),
        "invalidation_condition": _to_text(strategy.get("invalidation_condition"), "市场环境转弱或纪律信号反向时，本轮建议失效。"),
    }


def _candidate_from_row(row: Any, scan_state: Any = None, live_section: Any = None) -> dict:
    row_map = _as_mapping(row)
    scan = _as_mapping(scan_state)
    live = _as_mapping(live_section)
    candidate = _as_mapping(row_map.get("candidate")) or row_map
    score = _as_mapping(row_map.get("score")) or row_map
    return {
        "ticker": _to_text(candidate.get("ticker") or score.get("ticker")),
        "name": _to_text(candidate.get("name") or score.get("name")),
        "action_state": _to_text(score.get("battle_state") or row_map.get("action_state") or candidate.get("action_state"), "只观察"),
        "score": _to_number(score.get("total_score") or score.get("score") or row_map.get("score")),
        "trigger_condition": _to_text(
            score.get("trigger_condition")
            or row_map.get("trigger_condition")
            or score.get("one_sentence_conclusion")
            or row_map.get("summary"),
            "等待规则雷达触发条件确认。",
        ),
        "invalidation_condition": _to_text(
            score.get("invalidation_condition")
            or row_map.get("invalidation_condition")
            or score.get("fail_condition"),
            "市场转弱、候选评分下降或纪律信号反向时失效。",
        ),
        "source": _to_text(row_map.get("source") or scan.get("source") or live.get("source"), "下一票雷达缓存"),
        "updated_at": _to_text(row_map.get("updated_at") or row_map.get("generated_at") or scan.get("generated_at") or live.get("updated_at"), "暂无"),
    }


def extract_next_ticket_candidates(state: Any = None, live_packet: Any = None, limit: int = MAX_CANDIDATES) -> list[dict]:
    state_map = _as_mapping(state)
    radar_packet = _as_mapping(state_map.get("command_center_radar_packet"))
    if radar_packet.get("top_candidates"):
        enriched = radar_packet_service.build_command_center_radar_packet(
            {"command_center_radar_packet": radar_packet},
            live_packet=live_packet,
            limit=limit,
        )
        return _as_list(enriched.get("top_candidates"))[:limit]
    live = _as_mapping(live_packet)
    live_section = _as_mapping(live.get("next_ticket"))
    scan_state = _as_mapping(state_map.get("radar_scan_results"))
    rows = _as_list(live_section.get("top_candidates"))
    if not rows:
        rows = _as_list(scan_state.get("rule_rows") or scan_state.get("results"))
    candidates = []
    seen = set()
    for row in rows:
        item = radar_packet_service.normalize_radar_candidate(
            row,
            scan_packet=scan_state,
            live_section=live_section,
            rank=len(candidates) + 1,
        )
        key = item.get("ticker") or item.get("name")
        if not key or key in seen:
            continue
        seen.add(key)
        candidates.append(item)
    return candidates[:limit]


def _flatten_etf_candidates(candidates: Any) -> list[dict]:
    rows = []
    if isinstance(candidates, Mapping):
        for bucket, items in candidates.items():
            for item in _as_list(items):
                payload = _as_mapping(item)
                if payload:
                    payload.setdefault("bucket", bucket)
                    rows.append(payload)
    else:
        rows = [_as_mapping(item) for item in _as_list(candidates)]
    normalized = []
    for row in rows:
        if not row:
            continue
        normalized.append(
            {
                "code": _to_text(row.get("etf_code") or row.get("code") or row.get("ts_code")),
                "name": _to_text(row.get("etf_name") or row.get("name")),
                "bucket": _to_text(row.get("bucket") or row.get("theme"), "ETF"),
                "score": _to_number(row.get("total_score") or row.get("score")),
                "action_state": _to_text(row.get("action_state") or row.get("advice"), "只观察不追"),
            }
        )
    return normalized[:MAX_CANDIDATES]


def _current_margin_ratio_from_state(state: Mapping[str, Any], allocation: Mapping[str, Any]) -> int | float | None:
    explicit = _to_number(
        allocation.get("current_margin_debt_ratio")
        or state.get("current_margin_debt_ratio")
        or state.get("margin_current_margin_ratio")
        or state.get("margin_ratio")
    )
    if explicit is not None:
        return explicit
    margin_debt = _to_number(state.get("margin_debt"))
    total_asset = _to_number(state.get("margin_total_asset"))
    cash = _to_number(state.get("margin_cash_balance")) or 0
    stock_value = _to_number(state.get("margin_stock_value")) or 0
    etf_value = _to_number(state.get("margin_etf_value")) or 0
    if margin_debt is None:
        return None
    gross_assets = max(total_asset or 0, cash + stock_value + etf_value, margin_debt)
    net_asset = gross_assets - margin_debt
    if net_asset <= 0:
        return None
    ratio = margin_debt / net_asset * 100
    return round(ratio, 2)


def build_margin_etf_summary(state: Any = None, live_packet: Any = None, etf_packet: Any = None) -> dict:
    state_map = _as_mapping(state)
    live_section = _as_mapping(_as_mapping(live_packet).get("margin_etf"))
    etf = _as_mapping(etf_packet) or etf_packet_service.build_command_center_etf_packet(state_map, live_packet)
    allocation = _as_mapping(state_map.get("legacy_margin_etf_allocation_result"))
    candidates = _as_list(etf.get("recommended_etfs")) or _flatten_etf_candidates(allocation.get("selected_etf_candidates") or allocation.get("recommended_etfs"))
    watch_not_chase = etf.get("watch_not_chase") or allocation.get("watch_not_chase") or allocation.get("watch_not_chase_etfs") or []
    watch_not_chase_items = [_to_text(item) for item in _as_list(watch_not_chase)]
    watch_not_chase_items = [item for item in watch_not_chase_items if item]
    if not watch_not_chase_items:
        watch_not_chase_items = ["不追高 ETF；等待回踩、量能和风险线确认。"]
    current_margin_ratio = _to_number(etf.get("current_margin_ratio"))
    if current_margin_ratio is None:
        current_margin_ratio = _current_margin_ratio_from_state(state_map, allocation)
    return {
        "current_margin_ratio": current_margin_ratio,
        "recommended_margin_ratio": _to_number(etf.get("recommended_margin_ratio") or live_section.get("recommended_margin_ratio") or allocation.get("recommended_margin_ratio")),
        "recommended_cash_ratio": _to_number(etf.get("recommended_cash_ratio") or live_section.get("recommended_cash_ratio") or allocation.get("recommended_cash_ratio")),
        "today_main_direction": _to_text(etf.get("today_main_direction") or live_section.get("today_main_direction") or allocation.get("today_main_direction") or allocation.get("action_state"), "待刷新"),
        "recommended_etfs": candidates[:MAX_CANDIDATES],
        "watch_not_chase": watch_not_chase_items[:MAX_CANDIDATES],
    }


def build_today_action(decision_packet: Any = None) -> dict:
    decision = _as_mapping(decision_packet)
    return {
        "overall_action": _to_text(decision.get("overall_action"), "等待"),
        "risk_level": _to_text(decision.get("risk_level"), "中"),
        "market_bias": _to_text(decision.get("market_bias"), "未刷新"),
        "position_mode": _to_text(decision.get("position_mode"), "空仓等待"),
        "margin_mode": _to_text(decision.get("margin_mode"), "不使用融资"),
    }


def build_risk_alerts(decision_packet: Any = None, strategy_packet: Any = None, coverage: Any = None, errors: Any = None) -> dict:
    decision = _as_mapping(decision_packet)
    strategy = _as_mapping(strategy_packet)
    must_not_do = [_to_text(item) for item in _as_list(decision.get("must_not_do"))]
    must_not_do = [item for item in must_not_do if item] or ["不追高", "不满仓", "不在未刷新数据下加融资"]
    reduce_conditions = [_to_text(strategy.get("reduce_condition")) or _to_text(item) for item in _as_list(decision.get("next_validation_conditions"))]
    reduce_conditions = [item for item in reduce_conditions if item][:MAX_CANDIDATES]
    coverage_map = _as_mapping(coverage)
    data_gaps = [DATA_GAP_LABELS.get(key, key) for key, state in coverage_map.items() if state == "missing"]
    if _as_list(errors):
        data_gaps.append("存在刷新失败模块")
    return {
        "must_not_do": must_not_do[:5],
        "reduce_conditions": reduce_conditions,
        "data_gaps": data_gaps[:8] or ["暂无显式数据缺口"],
        "uses_cache": any(state == "cached" for state in coverage_map.values()),
    }


def _dedupe_text_items(values: Any, limit: int = MAX_ERRORS) -> list[str]:
    result = []
    seen = set()
    for value in _as_list(values):
        text = _to_text(value)
        if text and text not in seen:
            result.append(text)
            seen.add(text)
        if len(result) >= limit:
            break
    return result


def attach_data_capability_risk_alerts(risk_alerts: Any = None, data_capability_console: Any = None) -> dict:
    alerts = _as_mapping(risk_alerts)
    console = _as_mapping(data_capability_console)
    blockers = [_to_text(item) for item in _as_list(console.get("decision_blockers"))]
    blockers = [item for item in blockers if item]
    if not blockers:
        return alerts
    data_gaps = [_to_text(item) for item in _as_list(alerts.get("data_gaps"))]
    reduce_conditions = [_to_text(item) for item in _as_list(alerts.get("reduce_conditions"))]
    safe_mode = _to_text(console.get("safe_mode_text"))
    data_gaps.extend(blockers[:4])
    if safe_mode:
        reduce_conditions.insert(0, safe_mode)
    alerts["data_gaps"] = _dedupe_text_items(data_gaps, limit=8)
    alerts["reduce_conditions"] = _dedupe_text_items(reduce_conditions, limit=MAX_CANDIDATES)
    alerts["data_capability_mode"] = _to_text(console.get("decision_readiness_label"), "待检测")
    return alerts


def attach_recovery_priority_risk_alerts(risk_alerts: Any = None, data_recovery_center: Any = None) -> dict:
    alerts = _as_mapping(risk_alerts)
    center = _as_mapping(data_recovery_center)
    lanes = [_as_mapping(item) for item in _as_list(center.get("priority_lanes"))]
    active_lanes = [item for item in lanes if _to_number(item.get("count"))]
    if not active_lanes:
        alerts.setdefault("recovery_priority_items", [])
        alerts.setdefault("recovery_priority_summary", "暂无数据恢复优先级风险")
        alerts.setdefault("deepseek_called", False)
        return alerts

    priority_items = []
    for lane in active_lanes:
        label = _to_text(lane.get("label"), "恢复优先级")
        summary = _to_text(lane.get("summary"), "暂无")
        next_action = _to_text(lane.get("next_action"), "按队列手动恢复。")
        priority_items.append(
            {
                "key": _to_text(lane.get("key"), "p1"),
                "label": label,
                "tone": _to_text(lane.get("tone"), "missing"),
                "count": int(_to_number(lane.get("count")) or 0),
                "summary": summary,
                "next_action": next_action,
                "risk_text": f"{label}：{summary}。处理：{next_action}",
            }
        )

    must_not_do = [_to_text(item) for item in _as_list(alerts.get("must_not_do"))]
    reduce_conditions = [_to_text(item) for item in _as_list(alerts.get("reduce_conditions"))]
    data_gaps = [
        _to_text(item)
        for item in _as_list(alerts.get("data_gaps"))
        if _to_text(item) not in {"暂无", "暂无显式数据缺口"}
    ]
    lane_keys = {item["key"] for item in priority_items}
    if "p0" in lane_keys:
        must_not_do.insert(0, "P0 数据能力未恢复前，不放大仓位或把缺失当作无风险。")
    if "p1" in lane_keys:
        reduce_conditions.append("P1 缓存/近期无数据只能防白屏，不能当作实时事实。")
        alerts["uses_cache"] = True
    if "p2" in lane_keys:
        reduce_conditions.append("P2 旧工具 packet 未回流前，只把相关模块当待验证。")

    data_gaps.extend(item["risk_text"] for item in priority_items)
    alerts["must_not_do"] = _dedupe_text_items(must_not_do, limit=6)
    alerts["reduce_conditions"] = _dedupe_text_items(reduce_conditions, limit=MAX_CANDIDATES)
    alerts["data_gaps"] = _dedupe_text_items(data_gaps, limit=MAX_ERRORS)
    alerts["recovery_priority_items"] = priority_items[:3]
    alerts["recovery_priority_summary"] = "｜".join(item["risk_text"] for item in priority_items[:3])
    alerts["deepseek_called"] = False
    return alerts


def _hard_risk_item_text(item: Any) -> str:
    payload = _as_mapping(item)
    if not payload:
        return _to_text(item)
    risk_type = _to_text(payload.get("type") or payload.get("risk_type"), "硬风险")
    message = _to_text(payload.get("message") or payload.get("summary") or payload.get("title") or payload.get("risk"))
    date_text = _to_text(payload.get("date") or payload.get("ann_date") or payload.get("updated_at"))
    source = _to_text(payload.get("source"))
    parts = [risk_type]
    if message:
        parts.append(message)
    if date_text:
        parts.append(date_text)
    if source:
        parts.append(source)
    return "｜".join(parts)


def attach_hard_risk_risk_alerts(risk_alerts: Any = None, hard_risk_packet: Any = None) -> dict:
    alerts = _as_mapping(risk_alerts)
    hard = _as_mapping(hard_risk_packet)
    if not hard:
        return alerts
    status = _to_text(hard.get("status"))
    data_status = _to_text(hard.get("data_status"))
    risk_items = [_hard_risk_item_text(item) for item in _as_list(hard.get("risk_items"))]
    risk_items = [item for item in risk_items if item]
    risk_notes = [_to_text(item) for item in _as_list(hard.get("risk_notes"))]
    risk_notes = [item for item in risk_notes if item]
    must_not_do = [_to_text(item) for item in _as_list(alerts.get("must_not_do"))]
    reduce_conditions = [_to_text(item) for item in _as_list(alerts.get("reduce_conditions"))]
    data_gaps = [_to_text(item) for item in _as_list(alerts.get("data_gaps"))]
    if risk_items:
        must_not_do.insert(0, "公告/硬风险线索未复核前不加仓、不加融资。")
        reduce_conditions.extend(risk_items[:MAX_CANDIDATES])
        data_gaps.append("公告/硬风险存在待复核线索")
    elif status in {"failed", "partial"} or data_status in {"missing", "cached"}:
        must_not_do.append("公告/硬风险未验证前不新增风险暴露。")
        data_gaps.append(
            _to_text(
                hard.get("manual_required_text")
                or hard.get("summary")
                or "公告/硬风险仍待手动检测，不能当作无风险。",
            )
        )
    elif status == "ready":
        reduce_conditions.append("公告/硬风险无记录不等于无风险；公告正文和监管事实仍需复核。")
    alerts["must_not_do"] = _dedupe_text_items(must_not_do, limit=5)
    alerts["reduce_conditions"] = _dedupe_text_items(reduce_conditions, limit=MAX_CANDIDATES)
    alerts["data_gaps"] = _dedupe_text_items(data_gaps, limit=MAX_ERRORS)
    alerts["hard_risk_alerts"] = _dedupe_text_items(risk_items or risk_notes, limit=MAX_CANDIDATES)
    alerts["hard_risk_status"] = _to_text(hard.get("risk_state") or hard.get("summary") or status, "待验证")
    alerts["hard_risk_updated_at"] = _to_text(hard.get("updated_at") or hard.get("trade_date"), "暂无")
    return alerts


def build_home_action_snapshot(
    state: Any = None,
    target: str = "",
    position_profile: Any = None,
    live_packet: Any = None,
    decision_packet: Any = None,
    strategy_packet: Any = None,
    refresh_summary: Any = None,
    data_capability_packet: Any = None,
    facts_packet: Any = None,
    radar_packet: Any = None,
    now: Any = None,
) -> dict:
    state_map = _as_mapping(state)
    live = _as_mapping(live_packet or state_map.get("command_center_live_packet"))
    decision = _as_mapping(
        decision_packet
        or state_map.get("command_center_decision_packet")
        or state_map.get("command_center_decision_last_success")
    )
    strategy = _as_mapping(
        strategy_packet
        or state_map.get("strategy_execution_packet")
        or state_map.get("strategy_execution_last_success")
    )
    if data_capability_packet is None:
        data_capability_packet = resolve_data_capability_packet(state_map)
    if facts_packet is None:
        facts_packet = facts_packet_service.build_command_center_facts_packet(
            state_map,
            target=target,
            name=_to_text(_as_mapping(position_profile).get("name") or state_map.get("current_stock_name")),
        )
    if radar_packet is None:
        radar_packet = radar_packet_service.build_command_center_radar_packet(state_map, live)
    etf_packet = etf_packet_service.build_command_center_etf_packet(state_map, live)
    discipline_packet = discipline_packet_service.build_command_center_discipline_packet(
        state_map,
        live_packet=live,
        target=target,
    )
    market_packet = market_packet_service.build_command_center_market_packet(state_map, live)
    quant_packet = quant_packet_service.build_command_center_quant_packet(state_map, live, target=target)
    chip_packet = chip_packet_service.build_command_center_chip_packet(state_map, live, target=target)
    moneyflow_packet = moneyflow_packet_service.build_command_center_moneyflow_packet(state_map, live, target=target)
    dragon_tiger_packet = dragon_tiger_packet_service.build_command_center_dragon_tiger_packet(state_map, live, target=target)
    margin_packet = margin_packet_service.build_command_center_margin_packet(state_map, live, target=target)
    limit_emotion_packet = limit_emotion_packet_service.build_command_center_limit_emotion_packet(
        state_map,
        live,
        target=target,
    )
    hard_risk_packet = hard_risk_packet_service.build_command_center_hard_risk_packet(
        state_map,
        live,
        target=target,
    )
    refresh = _as_mapping(refresh_summary or state_map.get("command_center_refresh_summary"))
    timestamp = _to_text(
        refresh.get("finished_at")
        or refresh.get("updated_at")
        or decision.get("updated_at")
        or strategy.get("updated_at")
        or live.get("updated_at")
        or live.get("generated_at")
        or _now_iso(now)
    )
    errors = _extract_errors(live, refresh, decision, strategy)
    coverage = _packet_data_coverage(live, decision, strategy)
    deepseek_called = any(bool(_as_mapping(packet).get("deepseek_called")) for packet in (live, decision, strategy))
    data_capability_snapshot = build_data_capability_snapshot(data_capability_packet)
    facts_packet_snapshot = facts_packet_service.build_command_center_facts_packet(
        {"command_center_facts_packet": facts_packet},
        target=target,
    )
    a_share_capability_matrix = a_share_capability_matrix_service.build_a_share_capability_matrix(
        data_capability_snapshot,
        facts_packet_snapshot,
    )
    data_gap_report = data_gap_report_service.build_command_center_data_gap_report(
        data_capability_snapshot,
        facts_packet_snapshot,
        refresh_summary=refresh,
        live_packet=live,
        errors=errors,
    )
    data_issue_explainer = data_issue_explainer_service.build_data_issue_explainer_packet(
        data_capability_snapshot,
        data_gap_report,
        refresh_summary=refresh,
        errors=errors,
    )
    data_capability_console = data_capability_console_service.build_data_capability_console_packet(
        data_capability_snapshot,
        data_gap_report,
        data_issue_explainer=data_issue_explainer,
        refresh_summary=refresh,
        errors=errors,
    )
    data_health_ledger = _as_mapping(data_capability_console.get("data_health_ledger"))
    data_health_visibility_summary = data_health_ledger_service.build_data_health_visibility_summary(data_health_ledger)
    data_health_timeline = data_health_ledger_service.build_data_health_timeline(data_health_ledger)
    data_health_timeline_recovery_actions = build_data_health_timeline_recovery_actions(data_health_timeline)
    provider_data_capability_cockpit = build_provider_data_capability_cockpit(
        {
            "data_capability": data_capability_snapshot,
            "data_issue_explainer": data_issue_explainer,
            "data_health_ledger": data_health_ledger,
        }
    )
    a_share_professional_facts = _as_mapping(state_map.get("a_share_professional_facts"))
    a_share_user_data_diagnostic = legacy_a_share_debug_summary_service.build_user_data_diagnostic_view_model(
        verified_technical_facts=(
            _as_mapping(a_share_professional_facts.get("verified_technical_facts"))
            or _as_mapping(state_map.get("verified_technical_facts"))
            or _as_mapping(live.get("verified_technical_facts"))
        ),
        moneyflow_data=(
            _as_mapping(a_share_professional_facts.get("moneyflow"))
            or _as_mapping(state_map.get("moneyflow_data"))
            or _as_mapping(state_map.get("a_share_moneyflow_data"))
        ),
        dragon_data=(
            _as_mapping(a_share_professional_facts.get("dragon_tiger"))
            or _as_mapping(state_map.get("dragon_data"))
            or _as_mapping(state_map.get("a_share_dragon_tiger_data"))
        ),
        margin_data=(
            _as_mapping(a_share_professional_facts.get("margin"))
            or _as_mapping(state_map.get("margin_data"))
            or _as_mapping(state_map.get("a_share_margin_data"))
        ),
        limit_emotion_data=(
            _as_mapping(a_share_professional_facts.get("limit_emotion"))
            or _as_mapping(state_map.get("limit_emotion_data"))
            or _as_mapping(state_map.get("a_share_limit_emotion_data"))
        ),
        chip_radar_data=(
            _as_mapping(a_share_professional_facts.get("chip_radar"))
            or _as_mapping(state_map.get("command_center_chip_packet"))
            or chip_packet
        ),
        hard_risk_data=(
            _as_mapping(a_share_professional_facts.get("verified_hard_risks"))
            or _as_mapping(a_share_professional_facts.get("hard_risk"))
            or _as_mapping(state_map.get("command_center_hard_risk_packet"))
            or hard_risk_packet
        ),
    )
    data_recovery_actions = build_data_recovery_actions_snapshot(data_capability_console, data_issue_explainer)
    latest_recovery_result_notice = build_latest_recovery_result_notice(
        state_map,
        selected_tab=state_map.get("legacy_workspace_selected_tab"),
    )
    risk_alerts = attach_hard_risk_risk_alerts(
        attach_data_capability_risk_alerts(
            build_risk_alerts(decision, strategy, coverage, errors),
            data_capability_console,
        ),
        hard_risk_packet,
    )
    analysis_method_packet = (
        state_map.get("command_center_analysis_method_packet")
        or state_map.get("analysis_method_packet")
        or {}
    )
    projection_packet = (
        state_map.get("command_center_projection_packet")
        or state_map.get("projection_packet")
        or {}
    )
    position_map = _as_mapping(position_profile)
    market_profile_evidence = market_profile_summary_service.build_market_profile_evidence_strip(
        market_type=state_map.get("market_type") or position_map.get("market_type"),
        ticker=target or position_map.get("ticker"),
        name=position_map.get("name") or state_map.get("current_stock_name"),
        live_packet=live,
        decision_packet=decision,
        strategy_packet=strategy,
        home_snapshot=state_map.get("command_center_home_snapshot") or {},
        analysis_method_packet=analysis_method_packet,
    )
    snapshot = {
        "status": "ready",
        "is_empty": False,
        "timestamp": timestamp,
        "source": SNAPSHOT_SOURCE,
        "decision_packet": decision,
        "strategy_packet": strategy,
        "today_action": build_today_action(decision),
        "holding_action": build_holding_action(target=target, position_profile=position_profile, strategy_packet=strategy, state=state_map),
        "next_ticket_candidates": extract_next_ticket_candidates({"command_center_radar_packet": radar_packet}, live),
        "radar_packet": radar_packet_service.build_command_center_radar_packet(
            {"command_center_radar_packet": radar_packet},
            live_packet=live,
        ),
        "etf_packet": etf_packet,
        "discipline_packet": discipline_packet,
        "quant_packet": quant_packet,
        "chip_packet": chip_packet,
        "moneyflow_packet": moneyflow_packet,
        "dragon_tiger_packet": dragon_tiger_packet,
        "margin_packet": margin_packet,
        "limit_emotion_packet": limit_emotion_packet,
        "hard_risk_packet": hard_risk_packet,
        "a_share_fact_recovery_summary": {},
        "legacy_a_share_gap_summary": {},
        "margin_etf_summary": build_margin_etf_summary(state_map, live, etf_packet=etf_packet),
        "risk_alerts": risk_alerts,
        "data_coverage": coverage,
        "data_freshness": build_data_freshness(timestamp, errors, deepseek_called=deepseek_called),
        "data_capability": data_capability_snapshot,
        "a_share_capability_matrix": a_share_capability_matrix,
        "facts_packet": facts_packet_snapshot,
        "data_gap_report": data_gap_report,
        "data_issue_explainer": data_issue_explainer,
        "data_capability_console": data_capability_console,
        "data_health_ledger": data_health_ledger,
        "data_health_visibility_summary": data_health_visibility_summary,
        "command_center_data_health_visibility_summary": data_health_visibility_summary,
        "data_health_timeline": data_health_timeline,
        "command_center_data_health_timeline": data_health_timeline,
        "data_health_timeline_recovery_actions": data_health_timeline_recovery_actions,
        "command_center_data_health_timeline_recovery_actions": data_health_timeline_recovery_actions,
        "provider_data_capability_cockpit": provider_data_capability_cockpit,
        "a_share_user_data_diagnostic": a_share_user_data_diagnostic,
        "data_recovery_actions": data_recovery_actions,
        "legacy_a_share_fact_recovery_actions": [],
        "tool_recovery_actions": [],
        "next_ticket_evidence_recovery_actions": [],
        "data_recovery_center": {},
        "latest_recovery_result_notice": latest_recovery_result_notice,
        "recovery_result_status_strip": {},
        "command_center_recovery_result_timeline": {},
        "recovery_result_timeline": {},
        "market_packet": market_packet,
        "market_profile_evidence": market_profile_evidence,
        "analysis_method_packet": analysis_method_packet,
        "projection_packet": projection_packet,
        "errors": errors,
        "deepseek_called": deepseek_called,
        "safety_line": "本系统不自动交易，不保证收益；DeepSeek 只解释当前结构化结果。",
    }
    snapshot = attach_margin_etf_evidence_recovery_results(
        attach_next_ticket_evidence_recovery_results(snapshot)
    )
    has_payload = bool(decision or strategy or snapshot["next_ticket_candidates"] or snapshot["margin_etf_summary"]["recommended_etfs"])
    if not has_payload:
        empty = _empty_snapshot()
        empty["timestamp"] = timestamp
        empty["holding_action"] = snapshot["holding_action"]
        empty["data_coverage"] = coverage
        empty["risk_alerts"] = attach_hard_risk_risk_alerts(
            attach_data_capability_risk_alerts(
                build_risk_alerts(decision, strategy, coverage, errors),
                data_capability_console,
            ),
            hard_risk_packet,
        )
        empty["data_freshness"] = build_data_freshness("", errors, deepseek_called=deepseek_called)
        empty["data_capability"] = snapshot["data_capability"]
        empty["a_share_capability_matrix"] = snapshot["a_share_capability_matrix"]
        empty["facts_packet"] = snapshot["facts_packet"]
        empty["data_gap_report"] = snapshot["data_gap_report"]
        empty["data_issue_explainer"] = snapshot["data_issue_explainer"]
        empty["data_capability_console"] = snapshot["data_capability_console"]
        empty["data_health_ledger"] = snapshot["data_health_ledger"]
        empty["data_health_visibility_summary"] = snapshot["data_health_visibility_summary"]
        empty["command_center_data_health_visibility_summary"] = snapshot["command_center_data_health_visibility_summary"]
        empty["data_health_timeline"] = snapshot["data_health_timeline"]
        empty["command_center_data_health_timeline"] = snapshot["command_center_data_health_timeline"]
        empty["data_health_timeline_recovery_actions"] = snapshot["data_health_timeline_recovery_actions"]
        empty["command_center_data_health_timeline_recovery_actions"] = snapshot["command_center_data_health_timeline_recovery_actions"]
        empty["provider_data_capability_cockpit"] = snapshot["provider_data_capability_cockpit"]
        empty["a_share_user_data_diagnostic"] = snapshot["a_share_user_data_diagnostic"]
        empty["data_recovery_actions"] = snapshot["data_recovery_actions"]
        empty["legacy_a_share_fact_recovery_actions"] = build_legacy_a_share_fact_recovery_actions_snapshot(snapshot)
        empty["tool_recovery_actions"] = build_tool_recovery_actions_snapshot(snapshot)
        empty["next_ticket_evidence_recovery_actions"] = build_next_ticket_evidence_recovery_actions_snapshot(empty)
        empty["legacy_migration_map"] = legacy_migration_map_service.build_legacy_migration_map(
            empty,
            data_capability_packet=empty.get("data_capability") or {},
        )
        empty["data_recovery_center"] = build_home_data_recovery_center(empty)
        empty["old_workspace_packet_bridge"] = build_old_workspace_packet_bridge(empty)
        empty["recovery_result_status_strip"] = build_recovery_result_status_strip(
            empty,
            latest_notice=empty.get("latest_recovery_result_notice") or snapshot["latest_recovery_result_notice"],
            data_recovery_center=empty.get("data_recovery_center") or {},
        )
        empty["command_center_recovery_result_timeline"] = build_recovery_result_timeline(
            empty,
            latest_notice=empty.get("latest_recovery_result_notice") or snapshot["latest_recovery_result_notice"],
            status_strip=empty.get("recovery_result_status_strip") or {},
        )
        empty["recovery_result_timeline"] = empty["command_center_recovery_result_timeline"]
        empty["risk_alerts"] = attach_recovery_priority_risk_alerts(
            empty.get("risk_alerts") or {},
            empty.get("data_recovery_center") or {},
        )
        empty["latest_recovery_result_notice"] = snapshot["latest_recovery_result_notice"]
        empty["market_packet"] = snapshot["market_packet"]
        empty["market_profile_evidence"] = snapshot["market_profile_evidence"]
        empty["analysis_method_packet"] = snapshot["analysis_method_packet"]
        empty["projection_packet"] = snapshot["projection_packet"]
        empty["radar_packet"] = snapshot["radar_packet"]
        empty["etf_packet"] = snapshot["etf_packet"]
        empty["discipline_packet"] = snapshot["discipline_packet"]
        empty["quant_packet"] = snapshot["quant_packet"]
        empty["chip_packet"] = snapshot["chip_packet"]
        empty["moneyflow_packet"] = snapshot["moneyflow_packet"]
        empty["dragon_tiger_packet"] = snapshot["dragon_tiger_packet"]
        empty["margin_packet"] = snapshot["margin_packet"]
        empty["limit_emotion_packet"] = snapshot["limit_emotion_packet"]
        empty["hard_risk_packet"] = snapshot["hard_risk_packet"]
        empty["a_share_fact_recovery_summary"] = build_a_share_fact_recovery_summary(empty)
        empty["a_share_evidence_recovery_ledger"] = build_a_share_evidence_recovery_ledger(empty)
        empty["strategy_prerequisite_recovery_ledger"] = build_strategy_prerequisite_recovery_ledger(empty)
        empty["legacy_a_share_gap_summary"] = build_legacy_a_share_gap_summary(empty)
        empty["old_workspace_data_absence_ledger"] = build_old_workspace_data_absence_ledger(empty)
        empty["a_share_evidence_packet"] = evidence_summary_service.build_a_share_evidence_radar_view_model(empty)
        empty["command_center_evidence_radar_packet"] = empty["a_share_evidence_packet"]
        empty = attach_decision_loop_status(
            empty,
            data_capability_console=empty.get("data_capability_console") or {},
            provider_data_capability_cockpit=empty.get("provider_data_capability_cockpit") or {},
            old_workspace_packet_bridge=empty.get("old_workspace_packet_bridge") or {},
            analysis_method_packet=empty.get("analysis_method_packet") or {},
            projection_packet=empty.get("projection_packet") or {},
            strategy_packet=empty.get("strategy_packet") or {},
            decision_packet=empty.get("decision_packet") or {},
        )
        empty["errors"] = errors
        return empty
    snapshot["a_share_fact_recovery_summary"] = build_a_share_fact_recovery_summary(snapshot)
    snapshot["a_share_evidence_recovery_ledger"] = build_a_share_evidence_recovery_ledger(snapshot)
    snapshot["strategy_prerequisite_recovery_ledger"] = build_strategy_prerequisite_recovery_ledger(snapshot)
    snapshot["legacy_a_share_gap_summary"] = build_legacy_a_share_gap_summary(snapshot)
    snapshot["old_workspace_data_absence_ledger"] = build_old_workspace_data_absence_ledger(snapshot)
    snapshot["a_share_evidence_packet"] = evidence_summary_service.build_a_share_evidence_radar_view_model(snapshot)
    snapshot["command_center_evidence_radar_packet"] = snapshot["a_share_evidence_packet"]
    snapshot["legacy_a_share_fact_recovery_actions"] = build_legacy_a_share_fact_recovery_actions_snapshot(snapshot)
    snapshot["tool_recovery_actions"] = build_tool_recovery_actions_snapshot(snapshot)
    snapshot["next_ticket_evidence_recovery_actions"] = build_next_ticket_evidence_recovery_actions_snapshot(snapshot)
    snapshot["legacy_migration_map"] = legacy_migration_map_service.build_legacy_migration_map(
        snapshot,
        data_capability_packet=snapshot.get("data_capability") or {},
    )
    snapshot["data_recovery_center"] = build_home_data_recovery_center(snapshot)
    snapshot["old_workspace_packet_bridge"] = build_old_workspace_packet_bridge(snapshot)
    snapshot["recovery_result_status_strip"] = build_recovery_result_status_strip(
        snapshot,
        latest_notice=snapshot.get("latest_recovery_result_notice") or {},
        data_recovery_center=snapshot.get("data_recovery_center") or {},
    )
    snapshot["command_center_recovery_result_timeline"] = build_recovery_result_timeline(
        snapshot,
        latest_notice=snapshot.get("latest_recovery_result_notice") or {},
        status_strip=snapshot.get("recovery_result_status_strip") or {},
    )
    snapshot["recovery_result_timeline"] = snapshot["command_center_recovery_result_timeline"]
    snapshot["risk_alerts"] = attach_recovery_priority_risk_alerts(
        snapshot.get("risk_alerts") or {},
        snapshot.get("data_recovery_center") or {},
    )
    snapshot = attach_decision_loop_status(
        snapshot,
        data_capability_console=snapshot.get("data_capability_console") or {},
        analysis_method_packet=analysis_method_packet,
        projection_packet=projection_packet,
        strategy_packet=strategy,
        decision_packet=decision,
    )
    return sanitize_snapshot_payload(snapshot)


def has_action_snapshot_data(snapshot: Any) -> bool:
    payload = _as_mapping(snapshot)
    if not payload or payload.get("is_empty"):
        return False
    return bool(
        _as_mapping(payload.get("decision_packet"))
        or _as_mapping(payload.get("strategy_packet"))
        or _as_mapping(payload.get("market_packet")).get("data_status") == "ready"
        or _as_mapping(payload.get("quant_packet")).get("data_status") == "ready"
        or _as_mapping(payload.get("chip_packet")).get("data_status") == "ready"
        or _as_mapping(payload.get("moneyflow_packet")).get("data_status") == "ready"
        or _as_mapping(payload.get("dragon_tiger_packet")).get("data_status") == "ready"
        or _as_mapping(payload.get("margin_packet")).get("data_status") == "ready"
        or _as_mapping(payload.get("limit_emotion_packet")).get("data_status") == "ready"
        or _as_mapping(payload.get("hard_risk_packet")).get("data_status") == "ready"
        or _as_list(payload.get("next_ticket_candidates"))
        or _as_list(_as_mapping(payload.get("radar_packet")).get("top_candidates"))
        or _as_list(_as_mapping(payload.get("etf_packet")).get("recommended_etfs"))
        or _as_mapping(payload.get("discipline_packet")).get("data_status") == "ready"
        or _as_list(_as_mapping(payload.get("margin_etf_summary")).get("recommended_etfs"))
        or _as_list(_as_mapping(payload.get("facts_packet")).get("items"))
    )


def choose_home_action_snapshot(primary: Any, fallback: Any) -> dict:
    primary_map = _as_mapping(primary)
    fallback_map = _as_mapping(fallback)
    if has_action_snapshot_data(primary_map):
        return primary_map
    if has_action_snapshot_data(fallback_map):
        return fallback_map
    return primary_map or fallback_map or _empty_snapshot()


def update_home_action_snapshot(
    state: Any,
    target: str = "",
    position_profile: Any = None,
    live_packet: Any = None,
    decision_packet: Any = None,
    strategy_packet: Any = None,
    refresh_summary: Any = None,
    data_capability_packet: Any = None,
    facts_packet: Any = None,
    radar_packet: Any = None,
    path: str | Path | None = None,
    base_dir: str | Path | None = None,
) -> dict:
    snapshot = build_home_action_snapshot(
        state,
        target=target,
        position_profile=position_profile,
        live_packet=live_packet,
        decision_packet=decision_packet,
        strategy_packet=strategy_packet,
        refresh_summary=refresh_summary,
        data_capability_packet=data_capability_packet,
        facts_packet=facts_packet,
        radar_packet=radar_packet,
    )
    if isinstance(state, dict):
        state["command_center_home_snapshot"] = snapshot
    save_home_action_snapshot(snapshot, path=path, base_dir=base_dir)
    return snapshot
