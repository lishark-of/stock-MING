import ast
import copy
import json
import unittest
from pathlib import Path

import command_center_legacy_a_share_debug_summary as debug_summary


class CommandCenterLegacyAShareDebugSummaryTests(unittest.TestCase):
    def test_build_technical_summary_handles_missing_fields(self):
        facts = {
            "available": True,
            "latest_close": 12.3,
            "ma60_state": "站上",
            "missing": ["moneyflow", "dragon_tiger"],
        }
        before = copy.deepcopy(facts)

        summary = debug_summary.build_technical_summary(facts)

        self.assertEqual(facts, before)
        self.assertTrue(summary["available"])
        self.assertEqual(summary["latest_close"], "12.3")
        self.assertEqual(summary["ma60_state"], "站上")
        self.assertEqual(summary["missing"], "moneyflow、dragon_tiger")
        self.assertEqual(summary["rsi_14"], "暂无可验证数据")

    def test_build_fund_rows_detects_permission_and_stale_issues(self):
        moneyflow = {
            "available": False,
            "source": "Tushare moneyflow",
            "error": "无接口访问权限",
        }
        dragon = {
            "available": False,
            "warning": "近30日无数据，数据尚未更新",
        }
        margin = {"available": True, "ok": True, "date": "2026-06-03", "financing_balance_yi": 10.1}
        limit_emotion = {"available": True, "records_available": True, "limit_records": [{"type": "涨停"}]}

        rows, missing, permission_issues, stale_issues = debug_summary.build_fund_rows(
            moneyflow_data=moneyflow,
            dragon_data=dragon,
            margin_data=margin,
            limit_emotion_data=limit_emotion,
        )

        self.assertEqual(len(rows), 4)
        self.assertIn("moneyflow", missing)
        self.assertIn("dragon_tiger", missing)
        self.assertTrue(any("moneyflow" in item and "权限" in item for item in permission_issues))
        self.assertTrue(any("dragon_tiger" in item and "数据尚未更新" in item for item in stale_issues))
        margin_row = next(row for row in rows if row["name"] == "margin")
        self.assertTrue(margin_row["available"])
        self.assertEqual(margin_row["trade_date"], "2026-06-03")

    def test_build_packet_status_reports_triggered_fact_packets(self):
        status = debug_summary.build_packet_status(
            verified_technical_facts={"available": True},
            ai_context_packet="文本包含【已验证技术事实】",
            whale_fact_packet={"stock": "002008"},
            next_day_plan_fact_packet=None,
            single_stock_war_room_fact_packet={"stock": "002008"},
        )

        self.assertTrue(status["verified_technical_facts_available"])
        self.assertTrue(status["ai_context_packet_has_verified_technical_facts"])
        self.assertEqual(status["whale_fact_packet_status"], "已构造")
        self.assertEqual(status["next_day_plan_fact_packet_status"], "尚未触发")
        self.assertEqual(status["single_stock_war_room_fact_packet_status"], "已构造")

    def test_build_debug_view_model_is_json_friendly(self):
        view_model = debug_summary.build_legacy_a_share_debug_view_model(
            verified_technical_facts={"available": False, "missing": ["verified_technical_facts"]},
            moneyflow_data={"available": False, "message": "权限不足"},
            dragon_data={"available": False},
            margin_data={"available": True, "date": "2026-06-03"},
            limit_emotion_data={"available": False, "warning": "暂未取得可验证数据"},
            ai_context_packet="",
            whale_fact_packet=None,
            next_day_plan_fact_packet={"packet": True},
            single_stock_war_room_fact_packet=None,
        )

        self.assertIn("technical_rows", view_model)
        self.assertIn("fund_rows", view_model)
        self.assertIn("packet_status_rows", view_model)
        self.assertIn("missing_rows", view_model)
        self.assertIn("moneyflow", view_model["missing_summary"]["资金缺失项"])
        self.assertIn("权限", view_model["missing_summary"]["权限不足项"])
        self.assertIn("暂未取得", view_model["missing_summary"]["数据未更新项"])
        json.dumps(view_model, ensure_ascii=False)

    def test_user_data_diagnostic_explains_permission_issues(self):
        view_model = debug_summary.build_user_data_diagnostic_view_model(
            verified_technical_facts={"available": True},
            moneyflow_data={"available": False, "error": "无接口访问权限"},
            dragon_data={"available": True},
            margin_data={"available": True},
            limit_emotion_data={"available": True},
        )

        self.assertEqual(view_model["tone"], "warning")
        self.assertIn("权限不足", view_model["headline"])
        self.assertIn("Tushare 权限", view_model["next_action"])
        self.assertIn("页面打开不会自动请求", view_model["safe_mode_text"])
        item = next(item for item in view_model["items"] if item["key"] == "moneyflow")
        self.assertEqual(item["status"], "permission_denied")
        self.assertEqual(item["status_label"], "权限不足")
        self.assertEqual(item["writes_packet"], "command_center_moneyflow_packet")
        self.assertEqual(item["refresh_policy"], "button_gated")
        self.assertIn("A股数据能力检测", item["toolbox_entry"])
        self.assertFalse(item["deepseek_called"])
        self.assertEqual(view_model["recovery_actions"][0]["label"], "个股资金流")
        self.assertEqual(view_model["recovery_actions"][0]["writes_packet"], "command_center_moneyflow_packet")
        self.assertEqual(view_model["recovery_actions"][0]["legacy_tab"], "今日关注池")
        self.assertIn("主导航切到高级工具箱", view_model["recovery_actions"][0]["navigation_label"])
        self.assertFalse(view_model["recovery_actions"][0]["deepseek_called"])
        console = view_model["status_console"]
        self.assertEqual(console["title"], "A股数据能力控制台")
        self.assertEqual(console["decision_readiness_label"], "阻断加仓")
        self.assertIn("受限 1", console["summary"])
        by_group = {item["key"]: item for item in console["groups"]}
        self.assertEqual(by_group["permission_denied"]["items"], ["个股资金流"])
        self.assertEqual(by_group["available"]["count"], 3)
        self.assertFalse(console["deepseek_called"])
        json.dumps(view_model, ensure_ascii=False)

    def test_user_data_diagnostic_explains_stale_or_empty_data(self):
        view_model = debug_summary.build_user_data_diagnostic_view_model(
            verified_technical_facts={"available": False, "missing": ["verified_technical_facts"]},
            moneyflow_data={"available": False, "warning": "近5日暂未取得可验证数据"},
            dragon_data={"available": False, "warning": "数据尚未更新"},
            margin_data={"available": True},
            limit_emotion_data={"available": True},
        )

        self.assertEqual(view_model["tone"], "info")
        self.assertIn("暂未取得", view_model["headline"])
        self.assertIn("等待交易日数据发布", view_model["next_action"])
        self.assertGreaterEqual(view_model["counts"]["stale_or_empty"], 2)
        self.assertIn("技术缺失项", view_model["summary"])
        self.assertEqual(view_model["status_console"]["decision_readiness_label"], "谨慎验证")
        self.assertIn("暂无数据 2", view_model["status_console"]["summary"])

    def test_user_data_diagnostic_marks_all_available(self):
        view_model = debug_summary.build_user_data_diagnostic_view_model(
            verified_technical_facts={"available": True},
            moneyflow_data={"available": True},
            dragon_data={"available": True},
            margin_data={"available": True},
            limit_emotion_data={"available": True},
        )

        self.assertEqual(view_model["tone"], "success")
        self.assertIn("可用", view_model["headline"])
        self.assertEqual(view_model["counts"]["available"], 4)
        self.assertEqual(view_model["recovery_actions"], [])
        self.assertIn("暂无需要恢复", view_model["recovery_summary"])
        self.assertEqual(view_model["status_console"]["decision_readiness_label"], "可进入证据链")
        self.assertIn("可用 4", view_model["status_console"]["summary"])
        self.assertIn("DeepSeek 解释", view_model["next_action"])

    def test_forbidden_imports(self):
        tree = ast.parse(Path("command_center_legacy_a_share_debug_summary.py").read_text(encoding="utf-8"))
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module or "")

        forbidden = {
            "streamlit",
            "app",
            "pandas",
            "data_fetcher",
            "tushare_adapter",
            "akshare",
            "yfinance",
            "openai",
            "backtester",
            "command_center_service",
        }
        self.assertFalse(forbidden.intersection(imports))


if __name__ == "__main__":
    unittest.main()
