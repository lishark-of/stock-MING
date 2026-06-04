from __future__ import annotations

from collections.abc import Mapping
from numbers import Number
from typing import Any

import command_center_local_api_contract as local_api_contract
import command_center_local_api_preview as local_api_preview


READINESS_KIND = "command_center_desktop_frontend_readiness"

SURFACE_SPECS = [
    {
        "key": "home_action_snapshot",
        "label": "Home Action Snapshot",
        "description": "当前持仓、下一票、ETF/融资和风险警报的首页快照。",
        "required_any": ["command_center_home_snapshot"],
        "supporting_packets": ["latest_recovery_result_notice"],
        "next_action": "先保留本地快照；刷新今日基础数据后写入最新 snapshot。",
    },
    {
        "key": "decision_hero",
        "label": "今日总决策 Hero",
        "description": "总动作、风险等级、市场偏向、仓位模式和依据链。",
        "required_any": ["command_center_decision_packet"],
        "supporting_packets": ["command_center_analysis_method_packet", "command_center_projection_packet"],
        "next_action": "点击生成今日总决策，或从上次快照读取缓存结果。",
    },
    {
        "key": "projection_chart",
        "label": "5-10 日趋势推演",
        "description": "历史段、T0、三条未来路径、概率和路径风险。",
        "required_any": ["command_center_projection_packet"],
        "supporting_packets": ["command_center_analysis_method_packet", "command_center_evidence_radar_packet"],
        "next_action": "先用已有 packet 生成推演；缺数据时展示待验证路径。",
    },
    {
        "key": "analysis_methods",
        "label": "市场分析方法",
        "description": "A股 / 美股 / ETF 的适用方法和待验证项。",
        "required_any": ["command_center_analysis_method_packet"],
        "supporting_packets": ["command_center_live_packet"],
        "next_action": "确认 ticker 与市场类型，基于已有 packet 生成分析方法摘要。",
    },
    {
        "key": "strategy_lab",
        "label": "策略执行实验室",
        "description": "动作、置信度、条件、路径、纪律校验和风险预算。",
        "required_any": ["strategy_execution_packet"],
        "supporting_packets": ["command_center_discipline_packet", "command_center_evidence_radar_packet"],
        "next_action": "点击生成策略执行建议；数据不足时保持待刷新。",
    },
    {
        "key": "data_freshness",
        "label": "数据新鲜度条",
        "description": "今日已刷新、使用缓存、待刷新、部分失败和 DeepSeek 状态。",
        "required_any": ["command_center_refresh_summary", "command_center_live_packet"],
        "supporting_packets": ["command_center_data_capability_packet", "a_share_professional_data_capability"],
        "next_action": "刷新今日基础数据或查看数据能力状态，不自动重试接口。",
    },
    {
        "key": "next_ticket_candidates",
        "label": "下一票 Top3",
        "description": "当前候选、状态、触发条件、失效条件、数据来源和更新时间。",
        "required_any": ["command_center_radar_packet", "radar_scan_results"],
        "supporting_packets": ["command_center_dragon_tiger_packet", "command_center_moneyflow_packet"],
        "next_action": "把旧版下一票雷达结果继续回流到 command_center_radar_packet。",
    },
    {
        "key": "etf_margin_action",
        "label": "ETF / 融资动作",
        "description": "融资比例、现金比例、ETF 主方向、推荐 ETF 和不追高名单。",
        "required_any": ["command_center_etf_packet", "legacy_margin_etf_allocation_result"],
        "supporting_packets": ["command_center_margin_packet"],
        "next_action": "把旧版融资 ETF 结果继续回流到 command_center_etf_packet。",
    },
    {
        "key": "risk_alerts",
        "label": "风险警报",
        "description": "禁止动作、必须降风险条件、数据缺口和缓存风险。",
        "required_any": ["command_center_hard_risk_packet", "command_center_evidence_radar_packet"],
        "supporting_packets": ["command_center_limit_emotion_packet", "command_center_chip_packet"],
        "next_action": "优先回流硬风险、涨跌停情绪和筹码证据。",
    },
]


def _to_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip() or default
    if isinstance(value, (bool, Number)):
        return str(value)
    return str(value).strip() or default


def _as_mapping(value: Any) -> dict:
    return dict(value) if isinstance(value, Mapping) else {}


def _as_list(value: Any) -> list:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return []


def _has_mapping_payload(value: Any) -> bool:
    payload = _as_mapping(value)
    return bool(payload) and not bool(payload.get("is_empty"))


def _has_text_or_items(value: Any) -> bool:
    if isinstance(value, Mapping):
        return any(_has_text_or_items(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(_has_text_or_items(item) for item in value)
    return bool(_to_text(value))


def _packet_keys_for_surfaces() -> list[str]:
    keys = []
    seen = set()
    for surface in SURFACE_SPECS:
        for key in surface["required_any"] + surface.get("supporting_packets", []):
            if key not in seen:
                keys.append(key)
                seen.add(key)
    return keys


def _responses_by_key(bundle: Mapping[str, Any]) -> dict[str, dict]:
    result = {}
    for response in bundle.get("responses") or []:
        packet = _as_mapping(response)
        key = _to_text(packet.get("packet_key"))
        if key:
            result[key] = packet
    return result


def _home_snapshot_from_state(state: Any) -> dict:
    return _as_mapping(_as_mapping(state).get("command_center_home_snapshot"))


def _home_snapshot_fallback_payload(home_snapshot: Mapping[str, Any], packet_key: str) -> dict:
    if packet_key == "command_center_refresh_summary":
        data_freshness = _as_mapping(home_snapshot.get("data_freshness"))
        if _has_mapping_payload(data_freshness) and data_freshness.get("state") != "missing":
            return {
                "status": "cached",
                "source": "command_center_home_snapshot.data_freshness",
                "data_freshness": data_freshness,
            }
    if packet_key == "command_center_radar_packet":
        candidates = _as_list(home_snapshot.get("next_ticket_candidates"))
        radar_packet = _as_mapping(home_snapshot.get("radar_packet"))
        if candidates:
            return {
                "status": "cached",
                "source": "command_center_home_snapshot.next_ticket_candidates",
                "top_candidates": candidates,
                "display_count": len(candidates),
            }
        if _has_mapping_payload(radar_packet):
            return {**radar_packet, "source": radar_packet.get("source") or "command_center_home_snapshot.radar_packet"}
    if packet_key == "command_center_etf_packet":
        etf_packet = _as_mapping(home_snapshot.get("etf_packet"))
        margin_summary = _as_mapping(home_snapshot.get("margin_etf_summary"))
        recommended = _as_list(margin_summary.get("recommended_etfs"))
        if _has_mapping_payload(etf_packet):
            return {**etf_packet, "source": etf_packet.get("source") or "command_center_home_snapshot.etf_packet"}
        if recommended:
            return {
                "status": "cached",
                "source": "command_center_home_snapshot.margin_etf_summary",
                "recommended_etfs": recommended,
                "recommended_margin_ratio": margin_summary.get("recommended_margin_ratio"),
                "recommended_cash_ratio": margin_summary.get("recommended_cash_ratio"),
                "today_main_direction": margin_summary.get("today_main_direction"),
                "watch_not_chase": margin_summary.get("watch_not_chase") or [],
            }
    if packet_key == "command_center_hard_risk_packet":
        hard_risk_packet = _as_mapping(home_snapshot.get("hard_risk_packet"))
        risk_alerts = _as_mapping(home_snapshot.get("risk_alerts"))
        if _has_mapping_payload(hard_risk_packet):
            return {**hard_risk_packet, "source": hard_risk_packet.get("source") or "command_center_home_snapshot.hard_risk_packet"}
        if _has_text_or_items(risk_alerts):
            return {
                "status": "cached",
                "source": "command_center_home_snapshot.risk_alerts",
                "risk_alerts": risk_alerts,
            }
    return {}


def _merge_home_snapshot_fallbacks(state: Any, responses: dict[str, dict]) -> dict[str, dict]:
    home_snapshot = _home_snapshot_from_state(state)
    if not home_snapshot or home_snapshot.get("is_empty"):
        return responses
    result = dict(responses)
    for packet_key in [
        "command_center_refresh_summary",
        "command_center_radar_packet",
        "command_center_etf_packet",
        "command_center_hard_risk_packet",
    ]:
        existing = _as_mapping(result.get(packet_key))
        if _is_available(existing) and not _is_error(existing):
            continue
        fallback_payload = _home_snapshot_fallback_payload(home_snapshot, packet_key)
        if not fallback_payload:
            continue
        result[packet_key] = local_api_contract.build_packet_response_envelope(
            packet_key=packet_key,
            payload=fallback_payload,
            status=fallback_payload.get("status") or "cached",
            warnings=["using command_center_home_snapshot fallback for desktop readiness"],
            meta={
                "available": True,
                "preview_only": True,
                "preview_source": "command_center_home_snapshot",
                "fallback_for": packet_key,
            },
        )
    return result


def _is_available(response: Mapping[str, Any]) -> bool:
    meta = _as_mapping(response.get("meta"))
    return bool(meta.get("available"))


def _is_error(response: Mapping[str, Any]) -> bool:
    return _to_text(response.get("status")).lower() == "error"


def _surface_status(required_responses: list[dict]) -> str:
    available = [response for response in required_responses if _is_available(response)]
    errors = [response for response in required_responses if _is_error(response)]
    usable = [response for response in available if not _is_error(response)]
    if usable and errors:
        return "partial"
    if usable:
        return "ready"
    if errors:
        return "blocked"
    return "missing"


def _surface_tone(status: str) -> str:
    if status == "ready":
        return "ready"
    if status == "partial":
        return "partial"
    if status == "blocked":
        return "blocked"
    return "missing"


def _status_label(status: str) -> str:
    return {
        "ready": "可用于桌面首屏",
        "partial": "部分可用",
        "blocked": "数据/错误阻断",
        "missing": "待回流",
    }.get(status, "待验证")


def _surface_item(spec: Mapping[str, Any], responses: Mapping[str, dict]) -> dict:
    required_keys = list(spec.get("required_any") or [])
    support_keys = list(spec.get("supporting_packets") or [])
    required_responses = [_as_mapping(responses.get(key)) for key in required_keys]
    support_responses = [_as_mapping(responses.get(key)) for key in support_keys]
    status = _surface_status(required_responses)
    available_required = [key for key, response in zip(required_keys, required_responses) if _is_available(response)]
    available_support = [key for key, response in zip(support_keys, support_responses) if _is_available(response)]
    missing_required = [key for key, response in zip(required_keys, required_responses) if not _is_available(response)]
    error_packets = [
        key
        for key, response in zip(required_keys + support_keys, required_responses + support_responses)
        if _is_error(response)
    ]
    api_paths = [
        _to_text(_as_mapping(response.get("meta")).get("local_api_path") or response.get("path"))
        for response in required_responses + support_responses
        if response
    ]
    api_paths = [path for path in api_paths if path]
    return {
        "key": spec.get("key"),
        "label": spec.get("label"),
        "description": spec.get("description"),
        "status": status,
        "status_label": _status_label(status),
        "tone": _surface_tone(status),
        "required_any": required_keys,
        "supporting_packets": support_keys,
        "available_required_packets": available_required,
        "available_supporting_packets": available_support,
        "missing_required_packets": missing_required,
        "error_packets": error_packets,
        "api_paths": api_paths,
        "next_action": spec.get("next_action"),
        "deepseek_called": False,
        "external_call_policy": "not_triggered",
    }


def build_desktop_frontend_readiness(
    state: Any = None,
    include_legacy: bool = True,
) -> dict:
    packet_keys = _packet_keys_for_surfaces()
    preview_bundle = local_api_preview.build_local_api_preview_bundle(
        state=state,
        packet_keys=packet_keys,
        include_legacy=include_legacy,
        include_missing=True,
    )
    responses = _merge_home_snapshot_fallbacks(state, _responses_by_key(preview_bundle))
    surfaces = [_surface_item(spec, responses) for spec in SURFACE_SPECS]
    ready_count = sum(1 for item in surfaces if item["status"] == "ready")
    partial_count = sum(1 for item in surfaces if item["status"] == "partial")
    blocked_count = sum(1 for item in surfaces if item["status"] == "blocked")
    missing_count = sum(1 for item in surfaces if item["status"] == "missing")
    score = round(((ready_count + partial_count * 0.5) / len(surfaces)) * 100)
    if ready_count == len(surfaces):
        readiness_status = "ready"
    elif ready_count or partial_count:
        readiness_status = "partial"
    elif blocked_count:
        readiness_status = "blocked"
    else:
        readiness_status = "empty"
    blockers = [
        {
            "surface": item["key"],
            "label": item["label"],
            "status": item["status"],
            "missing_required_packets": item["missing_required_packets"],
            "error_packets": item["error_packets"],
            "next_action": item["next_action"],
        }
        for item in surfaces
        if item["status"] in {"missing", "blocked", "partial"}
    ]
    return {
        "contract_version": local_api_contract.CONTRACT_VERSION,
        "kind": READINESS_KIND,
        "title": "桌面交易指挥台首屏可用性",
        "summary": "检查 Home Snapshot、总决策、趋势推演、分析方法、策略实验室、下一票、ETF/融资和风险警报是否已有 packet 可给桌面前端消费。",
        "readiness_status": readiness_status,
        "readiness_score": score,
        "surface_count": len(surfaces),
        "ready_surface_count": ready_count,
        "partial_surface_count": partial_count,
        "blocked_surface_count": blocked_count,
        "missing_surface_count": missing_count,
        "surfaces": surfaces,
        "blockers": blockers,
        "preview_summary": {
            "response_count": preview_bundle.get("response_count", 0),
            "available_count": preview_bundle.get("available_count", 0),
            "missing_count": preview_bundle.get("missing_count", 0),
            "error_count": preview_bundle.get("error_count", 0),
        },
        "deepseek_called": False,
        "external_call_policy": "not_triggered",
    }


def build_desktop_frontend_readiness_view_model(state: Any = None) -> dict:
    readiness = build_desktop_frontend_readiness(state=state)
    return {
        "title": readiness["title"],
        "status": readiness["readiness_status"],
        "score": readiness["readiness_score"],
        "summary": readiness["summary"],
        "metrics": [
            {"label": "可用模块", "value": readiness["ready_surface_count"], "tone": "ready"},
            {"label": "部分可用", "value": readiness["partial_surface_count"], "tone": "partial"},
            {"label": "待回流", "value": readiness["missing_surface_count"], "tone": "missing"},
            {"label": "阻断", "value": readiness["blocked_surface_count"], "tone": "blocked"},
        ],
        "surfaces": readiness["surfaces"],
        "blockers": readiness["blockers"][:5],
        "deepseek_called": False,
        "external_call_policy": "not_triggered",
    }
