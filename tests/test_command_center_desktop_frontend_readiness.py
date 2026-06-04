import ast
import copy
import json
import unittest
from pathlib import Path

import command_center_desktop_frontend_readiness as readiness


FORBIDDEN_IMPORTS = {
    "streamlit",
    "app",
    "command_center_service",
    "strategy_execution_service",
    "command_center_decision_engine",
    "tushare_adapter",
    "tushare",
    "akshare",
    "yfinance",
    "data_fetcher",
    "backtester",
    "openai",
}


def mostly_ready_state():
    return {
        "command_center_home_snapshot": {"status": "ready"},
        "command_center_decision_packet": {"status": "ready", "overall_action": "只观察"},
        "command_center_projection_packet": {"status": "cached", "paths": [{"name": "中性路径"}]},
        "command_center_analysis_method_packet": {"status": "ready", "market": "A股"},
        "strategy_execution_packet": {"status": "ready", "action": "等待"},
        "command_center_refresh_summary": {"status": "ready", "last_success": "2026-06-04"},
        "command_center_radar_packet": {"status": "ready", "candidates": [{"ticker": "002008.SZ"}]},
        "command_center_etf_packet": {"status": "ready", "items": [{"ticker": "560780.SH"}]},
        "command_center_hard_risk_packet": {"status": "ready", "alerts": []},
    }


class CommandCenterDesktopFrontendReadinessTests(unittest.TestCase):
    def test_empty_state_reports_empty_readiness(self):
        packet = readiness.build_desktop_frontend_readiness({})
        dumped = json.dumps(packet, ensure_ascii=False)

        self.assertEqual(packet["kind"], readiness.READINESS_KIND)
        self.assertEqual(packet["readiness_status"], "empty")
        self.assertEqual(packet["readiness_score"], 0)
        self.assertEqual(packet["ready_surface_count"], 0)
        self.assertEqual(packet["missing_surface_count"], packet["surface_count"])
        self.assertFalse(packet["deepseek_called"])
        self.assertEqual(packet["external_call_policy"], "not_triggered")
        self.assertIn("Home Action Snapshot", dumped)

    def test_mostly_ready_state_reports_ready(self):
        packet = readiness.build_desktop_frontend_readiness(mostly_ready_state())

        self.assertEqual(packet["readiness_status"], "ready")
        self.assertEqual(packet["readiness_score"], 100)
        self.assertEqual(packet["ready_surface_count"], packet["surface_count"])
        self.assertFalse(packet["blockers"])

    def test_missing_legacy_surfaces_become_actionable_blockers(self):
        state = {
            "command_center_home_snapshot": {"status": "ready"},
            "command_center_decision_packet": {"status": "ready"},
            "command_center_projection_packet": {"status": "ready"},
            "command_center_analysis_method_packet": {"status": "ready"},
            "strategy_execution_packet": {"status": "ready"},
            "command_center_refresh_summary": {"status": "ready"},
        }
        packet = readiness.build_desktop_frontend_readiness(state)
        blockers = {item["surface"]: item for item in packet["blockers"]}

        self.assertEqual(packet["readiness_status"], "partial")
        self.assertIn("next_ticket_candidates", blockers)
        self.assertIn("etf_margin_action", blockers)
        self.assertIn("risk_alerts", blockers)
        self.assertIn("command_center_radar_packet", blockers["next_ticket_candidates"]["missing_required_packets"])
        self.assertIn("command_center_etf_packet", blockers["etf_margin_action"]["missing_required_packets"])
        self.assertIn("command_center_hard_risk_packet", blockers["risk_alerts"]["missing_required_packets"])

    def test_alternative_packets_can_satisfy_surface(self):
        state = {
            "command_center_home_snapshot": {"status": "ready"},
            "command_center_decision_packet": {"status": "ready"},
            "command_center_projection_packet": {"status": "ready"},
            "command_center_analysis_method_packet": {"status": "ready"},
            "strategy_execution_packet": {"status": "ready"},
            "command_center_live_packet": {"status": "ready"},
            "radar_scan_results": {"status": "ready"},
            "legacy_margin_etf_allocation_result": {"status": "ready"},
            "command_center_evidence_radar_packet": {"status": "ready"},
        }
        packet = readiness.build_desktop_frontend_readiness(state)
        surfaces = {item["key"]: item for item in packet["surfaces"]}

        self.assertEqual(surfaces["data_freshness"]["status"], "ready")
        self.assertEqual(surfaces["next_ticket_candidates"]["status"], "ready")
        self.assertEqual(surfaces["etf_margin_action"]["status"], "ready")
        self.assertEqual(surfaces["risk_alerts"]["status"], "ready")

    def test_home_snapshot_nested_sections_can_satisfy_home_surfaces(self):
        state = {
            "command_center_home_snapshot": {
                "status": "ready",
                "is_empty": False,
                "data_freshness": {"state": "today", "label": "今日已刷新"},
                "next_ticket_candidates": [{"ticker": "002008.SZ", "name": "大族激光"}],
                "margin_etf_summary": {
                    "recommended_margin_ratio": 25,
                    "recommended_etfs": [{"code": "560780.SH", "name": "半导体设备ETF"}],
                },
                "risk_alerts": {
                    "hard_risk_status": "待验证",
                    "data_gaps": ["公告风险待验证"],
                },
            },
            "command_center_decision_packet": {"status": "ready"},
            "command_center_projection_packet": {"status": "ready"},
            "command_center_analysis_method_packet": {"status": "ready"},
            "strategy_execution_packet": {"status": "ready"},
        }
        packet = readiness.build_desktop_frontend_readiness(state)
        surfaces = {item["key"]: item for item in packet["surfaces"]}

        self.assertEqual(surfaces["data_freshness"]["status"], "ready")
        self.assertIn("command_center_refresh_summary", surfaces["data_freshness"]["available_required_packets"])
        self.assertEqual(surfaces["next_ticket_candidates"]["status"], "ready")
        self.assertIn("command_center_radar_packet", surfaces["next_ticket_candidates"]["available_required_packets"])
        self.assertEqual(surfaces["etf_margin_action"]["status"], "ready")
        self.assertIn("command_center_etf_packet", surfaces["etf_margin_action"]["available_required_packets"])
        self.assertEqual(surfaces["risk_alerts"]["status"], "ready")
        self.assertIn("command_center_hard_risk_packet", surfaces["risk_alerts"]["available_required_packets"])

    def test_empty_home_snapshot_does_not_satisfy_nested_surfaces(self):
        state = {
            "command_center_home_snapshot": {
                "status": "empty",
                "is_empty": True,
                "data_freshness": {"state": "missing", "label": "待刷新"},
                "risk_alerts": {"data_gaps": ["暂无可执行候选。点击刷新今日基础数据生成。"]},
            },
            "command_center_decision_packet": {"status": "ready"},
            "command_center_projection_packet": {"status": "ready"},
            "command_center_analysis_method_packet": {"status": "ready"},
            "strategy_execution_packet": {"status": "ready"},
        }
        packet = readiness.build_desktop_frontend_readiness(state)
        surfaces = {item["key"]: item for item in packet["surfaces"]}

        self.assertEqual(surfaces["data_freshness"]["status"], "missing")
        self.assertEqual(surfaces["next_ticket_candidates"]["status"], "missing")
        self.assertEqual(surfaces["etf_margin_action"]["status"], "missing")
        self.assertEqual(surfaces["risk_alerts"]["status"], "missing")

    def test_error_packet_marks_surface_blocked(self):
        state = {
            "command_center_hard_risk_packet": {"status": "failed", "last_error": "permission denied"},
        }
        packet = readiness.build_desktop_frontend_readiness(state)
        risk = next(item for item in packet["surfaces"] if item["key"] == "risk_alerts")

        self.assertEqual(risk["status"], "blocked")
        self.assertIn("command_center_hard_risk_packet", risk["error_packets"])
        self.assertEqual(packet["readiness_status"], "blocked")

    def test_readiness_does_not_mutate_state_and_is_json_friendly(self):
        state = mostly_ready_state()
        before = copy.deepcopy(state)
        packet = readiness.build_desktop_frontend_readiness(state)
        view_model = readiness.build_desktop_frontend_readiness_view_model(state)

        self.assertEqual(state, before)
        json.dumps(packet, ensure_ascii=False)
        json.dumps(view_model, ensure_ascii=False)
        self.assertEqual(view_model["score"], 100)
        self.assertEqual(view_model["metrics"][0]["label"], "可用模块")

    def test_readiness_has_no_forbidden_imports(self):
        tree = ast.parse(Path("command_center_desktop_frontend_readiness.py").read_text(encoding="utf-8"))
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module or "")

        for name in FORBIDDEN_IMPORTS:
            self.assertNotIn(name, imports, f"Forbidden import in command_center_desktop_frontend_readiness.py: {name}")


if __name__ == "__main__":
    unittest.main()
