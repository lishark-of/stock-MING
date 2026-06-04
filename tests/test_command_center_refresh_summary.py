import ast
import copy
import json
import unittest
from pathlib import Path

import command_center_refresh_summary as summary


FORBIDDEN_IMPORTS = {
    "streamlit",
    "pywebview",
    "webview",
    "data_fetcher",
    "backtester",
    "tushare_adapter",
    "yfinance",
    "akshare",
    "tushare",
    "openai",
    "app",
    "command_center_service",
}


class CommandCenterRefreshSummaryTests(unittest.TestCase):
    def test_refresh_level_normalization_and_labels(self):
        self.assertEqual(summary.normalize_refresh_level(None), "unknown")
        self.assertEqual(summary.normalize_refresh_level("light"), "light")
        self.assertEqual(summary.normalize_refresh_level("auto_light"), "light")
        self.assertEqual(summary.normalize_refresh_level("standard"), "standard")
        self.assertEqual(summary.normalize_refresh_level("manual_basic"), "standard")
        self.assertEqual(summary.normalize_refresh_level("full"), "full")
        self.assertEqual(summary.normalize_refresh_level("manual_deep"), "full")
        self.assertEqual(summary.normalize_refresh_level("奇怪刷新"), "unknown")
        self.assertEqual(summary.refresh_level_label("light"), "轻量刷新")
        self.assertEqual(summary.refresh_level_label("standard"), "标准刷新")
        self.assertEqual(summary.refresh_level_label("full"), "完整刷新")
        self.assertEqual(summary.refresh_level_label("bad"), "未知刷新级别")

    def test_extract_refresh_errors_handles_multiple_shapes(self):
        errors = summary.extract_refresh_errors(
            {"errors": ["a", "b", ""]},
            {"errors": "a"},
            {"last_error": "b"},
            {"error": "c"},
            {"errors": [{"message": "m1"}, {"error": "m2"}]},
            None,
            object(),
        )

        self.assertEqual(errors, ["a", "b", "c", "m1", "m2"])
        self.assertTrue(all(isinstance(item, str) and item for item in errors))

    def test_extract_refresh_errors_limits_growth(self):
        errors = summary.extract_refresh_errors({"errors": [str(index) for index in range(20)]})

        self.assertEqual(len(errors), summary.MAX_ERRORS)

    def test_extract_completed_modules_handles_empty_and_ok_results(self):
        self.assertEqual(summary.extract_completed_modules(), [])
        self.assertEqual(summary.extract_completed_modules(object()), [])
        self.assertEqual(summary.extract_completed_modules({"results": "bad"}), [])

        completed = summary.extract_completed_modules(
            {
                "results": [
                    {"ok": True, "module": "市场环境"},
                    {"ok": False, "module": "量化推演"},
                    {"ok": True, "module": "市场环境"},
                    {"ok": True, "module_key": "discipline"},
                ]
            }
        )

        self.assertEqual(completed, ["市场环境", "discipline"])

    def test_extract_refresh_error_items_handles_multiple_shapes_without_mutation(self):
        payload = {
            "module": "市场环境",
            "updated_at": "2026-06-01T09:30:00",
            "source": "缓存",
            "errors": [
                "timeout",
                {"module": "量化推演", "message": "missing cache", "source": "本地缓存"},
                {"error": "bad packet", "updated_at": "2026-06-01T09:31:00"},
                "",
            ],
        }
        before = copy.deepcopy(payload)

        items = summary.extract_refresh_error_items(
            payload,
            {"last_error": "fallback error", "module": "纪律"},
            {"error": "hard fail"},
            max_errors=8,
        )

        self.assertEqual(payload, before)
        self.assertTrue(all(set(item) >= {"module", "message", "updated_at", "source"} for item in items))
        self.assertEqual(items[0]["module"], "市场环境")
        self.assertEqual(items[0]["message"], "timeout")
        self.assertEqual(items[1]["module"], "量化推演")
        self.assertEqual(items[1]["message"], "missing cache")
        self.assertIn("fallback error", [item["message"] for item in items])
        self.assertIn("hard fail", [item["message"] for item in items])
        json.dumps(items, ensure_ascii=False)

    def test_extract_refresh_error_items_limits_growth(self):
        items = summary.extract_refresh_error_items({"errors": [str(index) for index in range(20)]})

        self.assertEqual(len(items), summary.MAX_ERRORS)

    def test_summarize_refresh_result_covers_empty_success_partial_and_errors(self):
        empty = summary.summarize_refresh_result()
        self.assertEqual(empty["status"], "unknown")
        self.assertFalse(empty["ok"])

        ok = summary.summarize_refresh_result({"ok": True, "message": "done"})
        self.assertEqual(ok["status"], "ok")
        self.assertTrue(ok["ok"])
        self.assertEqual(ok["message"], "done")

        partial = summary.summarize_refresh_result({"ok": True, "errors": ["module failed"], "stale": True})
        self.assertEqual(partial["status"], "partial")
        self.assertEqual(partial["error_count"], 1)
        self.assertTrue(partial["stale"])
        self.assertEqual(partial["error_items"][0]["message"], "module failed")

        failed = summary.summarize_refresh_result({
            "ok": False,
            "last_success": "2026-06-01",
            "last_error": "timeout",
        })
        self.assertEqual(failed["status"], "failed")
        self.assertEqual(failed["last_success"], "2026-06-01")
        self.assertEqual(failed["last_error"], "timeout")

        bad = summary.summarize_refresh_result(object())
        self.assertEqual(bad["status"], "unknown")
        json.dumps(bad, ensure_ascii=False)

    def test_summarize_refresh_result_includes_completed_modules_and_error_items(self):
        result = {
            "ok": True,
            "results": [
                {"ok": True, "module": "市场环境"},
                {"ok": True, "module": "纪律"},
                {"ok": False, "module": "下一票"},
            ],
            "errors": [{"module": "下一票", "message": "scan skipped"}],
        }

        payload = summary.summarize_refresh_result(result)

        self.assertEqual(payload["completed_modules"], ["市场环境", "纪律"])
        self.assertEqual(payload["error_items"][0]["module"], "下一票")
        self.assertEqual(payload["error_items"][0]["message"], "scan skipped")
        self.assertEqual(payload["error_count"], 1)

    def test_module_statuses_are_json_friendly_and_do_not_mutate_input(self):
        live_packet = {
            "market": {"stale": False, "last_success": "2026-06-01", "status": "已刷新"},
            "etf": {"stale": True, "last_error": "timeout"},
            "next_ticket": {"errors": ["scan skipped"]},
        }
        before = copy.deepcopy(live_packet)

        statuses = summary.summarize_module_refresh_statuses(live_packet)

        self.assertEqual(live_packet, before)
        self.assertEqual([item["key"] for item in statuses], ["market", "etf", "next_ticket"])
        status_by_key = {item["key"]: item for item in statuses}
        self.assertEqual(status_by_key["market"]["status"], "ok")
        self.assertEqual(status_by_key["etf"]["status"], "failed")
        self.assertTrue(status_by_key["etf"]["stale"])
        self.assertEqual(status_by_key["etf"]["last_error"], "timeout")
        self.assertEqual(status_by_key["next_ticket"]["error"], "scan skipped")
        json.dumps(statuses, ensure_ascii=False)

    def test_build_refresh_summary_view_model(self):
        live_packet = {
            "market": {"status": "已刷新", "is_fresh": True},
            "next_ticket": {"errors": ["scan skipped"]},
        }

        view_model = summary.build_refresh_summary_view_model(
            live_packet=live_packet,
            refresh_result={"ok": True},
            refresh_level="light",
            generated_at="2026-06-01T09:30:00+09:00",
        )

        self.assertEqual(view_model["refresh_level"], "light")
        self.assertEqual(view_model["refresh_level_label"], "轻量刷新")
        self.assertIn("summary", view_model)
        self.assertIn("module_statuses", view_model)
        self.assertIn("errors", view_model)
        self.assertIn("completed_modules", view_model)
        self.assertIn("error_items", view_model)
        self.assertTrue(view_model["has_errors"])
        self.assertEqual(view_model["generated_at"], "2026-06-01T09:30:00+09:00")
        json.dumps(view_model, ensure_ascii=False)

    def test_build_refresh_summary_view_model_keeps_new_fields_json_friendly(self):
        live_packet = {
            "market": {"status": "已刷新", "is_fresh": True},
            "next_ticket": {"errors": [{"message": "scan skipped", "module": "下一票"}]},
        }
        before = copy.deepcopy(live_packet)

        view_model = summary.build_refresh_summary_view_model(
            live_packet=live_packet,
            refresh_result={
                "ok": True,
                "results": [{"ok": True, "module": "市场环境"}],
                "errors": [{"module": "量化推演", "message": "cache missing"}],
            },
            refresh_level="light",
            generated_at="2026-06-01T09:30:00+09:00",
        )

        self.assertEqual(live_packet, before)
        self.assertEqual(view_model["completed_modules"], ["市场环境"])
        self.assertEqual(view_model["error_items"][0]["module"], "量化推演")
        self.assertTrue(view_model["has_errors"])
        json.dumps(view_model, ensure_ascii=False)

    def test_a_share_fact_recovery_summary_is_json_friendly(self):
        recovery_summary = {
            "summary": "A股事实 5 项：已回流 2｜仍受限 1｜待验证 2",
            "tone": "failed",
            "recovered_count": "2",
            "blocked_count": "1",
            "waiting_count": "2",
            "total_count": "5",
            "next_action": "优先处理涨跌停情绪。",
            "items": [
                {
                    "key": "moneyflow",
                    "label": "个股资金流",
                    "recovery_state": "recovered",
                    "status_label": "可用",
                    "packet_status_text": "已回流｜可用｜command_center_moneyflow_packet",
                    "writes_packet": "command_center_moneyflow_packet",
                },
                {
                    "key": "limit_emotion",
                    "label": "涨跌停情绪",
                    "recovery_state": "blocked",
                    "status_label": "权限不足",
                    "diagnostic_answer": "limit_cpt_list 权限不足，不是没搜到行情。",
                    "next_action": "进入数据恢复中心手动检测。",
                    "toolbox_entry": "高级工具箱 / 数据源体检",
                    "workspace_target": "高级工具箱（旧版保留）",
                    "workspace_state_key": "workspace_mode_v2",
                    "legacy_tab": "数据源体检",
                    "legacy_tab_state_key": "legacy_workspace_selected_tab",
                    "navigation_label": "主导航切到高级工具箱（旧版保留）→ 高级工具模块选择数据源体检。",
                    "refresh_policy": "button_gated",
                },
            ],
            "deepseek_called": False,
        }
        before = copy.deepcopy(recovery_summary)

        payload = summary.summarize_a_share_fact_recovery(recovery_summary)

        self.assertEqual(recovery_summary, before)
        self.assertEqual(payload["summary"], "A股事实 5 项：已回流 2｜仍受限 1｜待验证 2")
        self.assertEqual(payload["blocked_count"], 1)
        self.assertEqual(payload["items"][1]["label"], "涨跌停情绪")
        self.assertIn("权限不足", payload["items"][1]["diagnostic_answer"])
        self.assertEqual(payload["items"][1]["legacy_tab"], "数据源体检")
        self.assertEqual(payload["items"][1]["workspace_state_key"], "workspace_mode_v2")
        self.assertEqual(payload["items"][1]["refresh_policy"], "button_gated")
        self.assertFalse(payload["deepseek_called"])
        json.dumps(payload, ensure_ascii=False)

    def test_refresh_view_model_surfaces_a_share_fact_recovery_status(self):
        view_model = summary.build_refresh_summary_view_model(
            live_packet={"market": {"status": "已刷新", "is_fresh": True}},
            refresh_result={"ok": True, "results": [{"ok": True, "module": "市场环境"}]},
            a_share_fact_recovery_summary={
                "recovered_count": 1,
                "blocked_count": 1,
                "waiting_count": 3,
                "total_count": 5,
                "items": [
                    {
                        "key": "dragon_tiger",
                        "label": "龙虎榜",
                        "recovery_state": "blocked",
                        "status_label": "本会话跳过",
                    }
                ],
                "deepseek_called": False,
            },
        )

        self.assertIn("A股事实 5 项", view_model["a_share_fact_recovery_summary"])
        self.assertEqual(view_model["a_share_fact_recovery"]["blocked_count"], 1)
        self.assertEqual(view_model["a_share_fact_recovery_items"][0]["label"], "龙虎榜")
        self.assertTrue(view_model["has_a_share_fact_blockers"])
        self.assertTrue(view_model["has_a_share_fact_waiting"])
        self.assertFalse(view_model["a_share_fact_recovery"]["deepseek_called"])
        json.dumps(view_model, ensure_ascii=False)

    def test_refresh_view_model_surfaces_latest_recovery_result_notice(self):
        view_model = summary.build_refresh_summary_view_model(
            refresh_result={"ok": True},
            latest_recovery_result_notice={
                "status": "recovered",
                "tone": "ready",
                "title": "A股数据恢复结果已回流",
                "label": "个股资金流",
                "message": "个股资金流：可用｜已读取到最近资金流数据。",
                "next_action": "继续查看 Home Action Snapshot。",
                "writes_packet": "command_center_moneyflow_packet",
                "updated_at": "2026-06-03T10:05:00",
                "source": "Tushare moneyflow",
                "source_type": "a_share_diagnostic",
                "external_call_policy": "button_gated",
                "deepseek_called": False,
            },
        )

        notice = view_model["latest_recovery_result_notice"]
        self.assertTrue(view_model["has_latest_recovery_result"])
        self.assertIn("A股数据恢复结果已回流", view_model["latest_recovery_result_summary"])
        self.assertEqual(notice["writes_packet"], "command_center_moneyflow_packet")
        self.assertEqual(notice["external_call_policy"], "button_gated")
        self.assertFalse(notice["deepseek_called"])
        json.dumps(view_model, ensure_ascii=False)

    def test_a_share_fact_recovery_bad_counts_do_not_raise(self):
        payload = summary.summarize_a_share_fact_recovery(
            {
                "recovered_count": "bad",
                "blocked_count": object(),
                "waiting_count": None,
                "items": [{"label": "筹码", "recovery_state": "waiting"}],
            }
        )

        self.assertEqual(payload["recovered_count"], 0)
        self.assertEqual(payload["blocked_count"], 0)
        self.assertEqual(payload["waiting_count"], 1)
        self.assertIn("待验证 1", payload["summary"])
        json.dumps(payload, ensure_ascii=False)

    def test_empty_none_and_non_mapping_inputs_do_not_raise(self):
        for value in (None, {}, object(), [], "bad packet"):
            self.assertIsInstance(summary.summarize_refresh_result(value), dict)
            self.assertIsInstance(summary.summarize_module_refresh_statuses(value), list)
            self.assertIsInstance(summary.build_refresh_summary_view_model(live_packet=value), dict)

    def test_forbidden_imports_are_absent(self):
        tree = ast.parse(Path("command_center_refresh_summary.py").read_text())
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module or "")

        for name in FORBIDDEN_IMPORTS:
            self.assertNotIn(name, imports, f"Forbidden import in command_center_refresh_summary.py: {name}")


if __name__ == "__main__":
    unittest.main()
