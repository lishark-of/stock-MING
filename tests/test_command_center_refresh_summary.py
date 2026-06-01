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
        self.assertTrue(view_model["has_errors"])
        self.assertEqual(view_model["generated_at"], "2026-06-01T09:30:00+09:00")
        json.dumps(view_model, ensure_ascii=False)

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
