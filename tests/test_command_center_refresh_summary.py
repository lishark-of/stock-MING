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

    def test_user_refresh_summary_translates_step_statuses(self):
        view_model = summary.build_refresh_summary_view_model(
            refresh_result={
                "finished_at": "2026-06-07T10:00:08",
                "deepseek_called": False,
                "results": [
                    {"module": "市场环境", "status": "completed", "ok": True, "duration_seconds": 2.14},
                    {"module": "ETF 配置", "status": "cached", "ok": True, "duration_seconds": 0.33},
                    {"module": "下一票雷达", "status": "empty", "ok": True, "duration_seconds": 1.0},
                    {"module": "纪律校验", "status": "failed", "ok": False, "error": "cache missing", "duration_seconds": 0.9},
                    {"module": "持仓行情", "status": "timeout", "ok": True, "duration_seconds": 8.01},
                ],
            }
        )

        items = {item["label"]: item for item in view_model["user_summary"]["step_items"]}
        self.assertEqual(items["市场环境"]["status_label"], "完成")
        self.assertEqual(items["ETF 配置"]["status_label"], "使用缓存")
        self.assertEqual(items["下一票雷达"]["status_label"], "无可执行候选")
        self.assertEqual(items["纪律校验"]["status_label"], "失败")
        self.assertEqual(items["持仓行情"]["status_label"], "超时")
        self.assertEqual(items["市场环境"]["duration"], "2.1s")
        self.assertIn("本轮轻量雷达未产生可执行候选", items["下一票雷达"]["message"])
        self.assertIn("cache missing", items["纪律校验"]["message"])
        json.dumps(view_model, ensure_ascii=False)

    def test_full_refresh_steps_standardizes_results(self):
        steps = summary.build_full_refresh_steps(
            {
                "finished_at": "2026-06-07T10:00:08",
                "deepseek_called": False,
                "results": [
                    {
                        "module_key": "market",
                        "module": "市场环境",
                        "status": "completed",
                        "ok": True,
                        "started_at": "2026-06-07T10:00:00",
                        "finished_at": "2026-06-07T10:00:02",
                        "duration_seconds": 2.14,
                        "message": "市场环境完成。",
                    },
                    {
                        "module_key": "next_ticket",
                        "module": "下一票雷达",
                        "status": "empty",
                        "ok": True,
                        "duration_seconds": 1,
                    },
                    {
                        "module": "DeepSeek 综合解释",
                        "key": "deepseek",
                        "status": "completed",
                    },
                ],
            }
        )

        by_key = {item["key"]: item for item in steps}
        self.assertIn("market", by_key)
        self.assertIn("next_ticket", by_key)
        self.assertNotIn("deepseek", by_key)
        self.assertEqual(by_key["market"]["name"], "市场环境")
        self.assertEqual(by_key["market"]["status"], "completed")
        self.assertEqual(by_key["market"]["label"], "完成")
        self.assertEqual(by_key["market"]["duration_seconds"], 2.14)
        self.assertIn("started_at", by_key["market"])
        self.assertIn("finished_at", by_key["market"])
        self.assertTrue(by_key["market"]["affects_decision"])
        self.assertEqual(by_key["next_ticket"]["label"], "无可执行候选")
        self.assertIn("本轮轻量雷达未产生可执行候选", by_key["next_ticket"]["message"])
        json.dumps(steps, ensure_ascii=False)

    def test_full_refresh_steps_preserve_failed_cached_and_missing_fields(self):
        steps = summary.build_full_refresh_steps(
            {
                "results": [
                    {"module": "ETF 配置", "status": "cached", "duration_seconds": 0.33},
                    {"module": "纪律校验", "status": "failed", "ok": False, "error": "cache missing"},
                    {"module": None, "duration_seconds": "bad"},
                ]
            }
        )

        by_name = {item["name"]: item for item in steps}
        self.assertEqual(by_name["ETF 配置"]["key"], "etf")
        self.assertEqual(by_name["ETF 配置"]["label"], "使用缓存")
        self.assertEqual(by_name["纪律校验"]["status"], "failed")
        self.assertEqual(by_name["纪律校验"]["label"], "失败")
        self.assertEqual(by_name["纪律校验"]["error"], "cache missing")
        self.assertEqual(by_name["纪律校验"]["duration_seconds"], 0.0)
        self.assertTrue(all({"key", "name", "status", "label", "duration_seconds"} <= set(item) for item in steps))
        json.dumps(steps, ensure_ascii=False)

    def test_user_refresh_summary_reads_full_refresh_steps_first(self):
        view_model = summary.build_refresh_summary_view_model(
            refresh_result={
                "results": [{"module": "市场环境", "status": "completed", "ok": True}],
                "full_refresh_steps": [
                    {
                        "name": "下一票雷达",
                        "key": "next_ticket",
                        "status": "empty",
                        "label": "无可执行候选",
                        "duration_seconds": 1.2,
                    }
                ],
            }
        )

        items = view_model["user_summary"]["step_items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["label"], "下一票雷达")
        self.assertEqual(items[0]["status_label"], "无可执行候选")

    def test_user_refresh_summary_sanitizes_internal_terms(self):
        view_model = summary.build_refresh_summary_view_model(
            refresh_result={
                "deepseek_called": False,
                "summary": "满血数据刷新完成：已执行 manual_basic 链路，并回流 provider capability 状态。",
                "results": [
                    {
                        "module": "command_center_next_ticket_packet",
                        "status": "completed",
                        "ok": True,
                        "duration_seconds": 0.2,
                        "message": "provider packet registry 已回流 command_center_radar_packet",
                    }
                ],
            }
        )

        user_summary = view_model["user_summary"]
        visible_text = json.dumps(
            {
                "display_lines": user_summary["display_lines"],
                "step_items": [
                    {
                        "label": item["label"],
                        "status_label": item["status_label"],
                        "message": item["message"],
                    }
                    for item in user_summary["step_items"]
                ],
            },
            ensure_ascii=False,
        ).lower()
        for forbidden in ("command_center", "packet", "provider", "registry"):
            self.assertNotIn(forbidden, visible_text)

    def test_user_refresh_summary_deepseek_status_appears_once(self):
        user_summary = summary.build_user_refresh_summary(
            {
                "deepseek_called": False,
                "results": [{"module": "市场环境", "status": "ready", "ok": True}],
            }
        )

        visible_lines = "\n".join(user_summary["display_lines"])
        self.assertEqual(visible_lines.count("DeepSeek"), 1)
        self.assertIn("DeepSeek：未调用", visible_lines)

    def test_user_data_capability_summary_counts_and_impact(self):
        payload = summary.build_user_data_capability_summary(
            {
                "data_capability_status_groups": {
                    "available": ["yfinance 行情", "Supabase 记忆"],
                    "failed": ["AkShare 资金穿透"],
                    "no_permission": ["Tushare 融资融券"],
                    "cached": ["ETF 配置"],
                }
            }
        )

        self.assertIn("可用 2", payload["line"])
        self.assertIn("失败 1", payload["line"])
        self.assertIn("权限不足 1", payload["line"])
        self.assertEqual(payload["impact"], "高")
        by_label = {item["label"]: item["status"] for item in payload["items"]}
        self.assertEqual(by_label["行情数据"], "已可用")
        self.assertEqual(by_label["资金数据"], "失败")
        self.assertEqual(by_label["ETF 数据"], "使用缓存")
        self.assertEqual(by_label["云端记忆"], "已可用")

    def test_user_refresh_summary_missing_fields_do_not_raise(self):
        for value in (None, {}, {"results": [object(), {"module": None, "duration_seconds": "bad"}]}):
            payload = summary.build_user_refresh_summary(value)
            self.assertIsInstance(payload, dict)
            json.dumps(payload, ensure_ascii=False)

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
