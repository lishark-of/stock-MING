import unittest
from pathlib import Path

import command_center_legacy_a_share_auto_hydrate as auto_hydrate


def _specs(keys=("moneyflow",)):
    return [
        {
            "key": key,
            "label": auto_hydrate.MODULE_LABELS.get(key, key),
            "source": "Tushare",
            "packet_key": auto_hydrate.COMMAND_CENTER_PACKET_KEYS.get(key, f"command_center_{key}_packet"),
            "legacy_packet_key": auto_hydrate.LEGACY_PACKET_KEYS.get(key, f"legacy_{key}_packet"),
        }
        for key in keys
    ]


class LegacyAShareAutoHydrateTests(unittest.TestCase):
    def test_entering_a_share_diagnostic_generates_packet(self):
        state = {}
        calls = []

        def moneyflow_handler(**kwargs):
            calls.append(kwargs["target"])
            state["command_center_moneyflow_packet"] = {
                "status": "ready",
                "data_status": "ready",
                "updated_at": "2026-06-05T09:30:00",
            }
            return {
                "item": {
                    "capability_state": "available",
                    "label": "资金流",
                    "checked_at": "2026-06-05T09:30:00",
                },
                "deepseek_called": False,
            }

        packet = auto_hydrate.execute_auto_hydrate(
            state,
            target="002008",
            market_type="A股",
            module_specs=_specs(),
            handlers={"moneyflow": moneyflow_handler},
            now_ts=1000,
            now_text="2026-06-05T09:30:00",
        )

        self.assertEqual(calls, ["002008"])
        self.assertEqual(packet["modules"][0]["status"], "available")
        self.assertEqual(state[auto_hydrate.STATUS_KEY], packet)
        self.assertFalse(packet["deepseek_called"])

    def test_same_fingerprint_within_ttl_does_not_repeat_handler(self):
        state = {}
        calls = []

        def handler(**kwargs):
            calls.append(kwargs["target"])
            return {"item": {"capability_state": "available", "label": "资金流"}, "deepseek_called": False}

        auto_hydrate.execute_auto_hydrate(
            state,
            target="002008",
            market_type="A股",
            module_specs=_specs(),
            handlers={"moneyflow": handler},
            ttl_seconds=600,
            now_ts=1000,
        )
        packet = auto_hydrate.execute_auto_hydrate(
            state,
            target="002008",
            market_type="A股",
            module_specs=_specs(),
            handlers={"moneyflow": handler},
            ttl_seconds=600,
            now_ts=1100,
        )

        self.assertEqual(calls, ["002008"])
        self.assertTrue(packet["skipped_by_ttl"])
        self.assertEqual(packet["decision"]["reason"], "ttl_active")

    def test_ticker_change_rehydrates(self):
        state = {}
        calls = []

        def handler(**kwargs):
            calls.append(kwargs["target"])
            return {"item": {"capability_state": "available", "label": "资金流"}, "deepseek_called": False}

        for target in ["002008", "600519"]:
            auto_hydrate.execute_auto_hydrate(
                state,
                target=target,
                market_type="A股",
                module_specs=_specs(),
                handlers={"moneyflow": handler},
                ttl_seconds=600,
                now_ts=1000,
            )

        self.assertEqual(calls, ["002008", "600519"])
        self.assertEqual(state[auto_hydrate.STATUS_KEY]["decision"]["reason"], "fingerprint_changed")

    def test_force_refresh_bypasses_ttl(self):
        state = {}
        calls = []

        def handler(**kwargs):
            calls.append(kwargs["target"])
            return {"item": {"capability_state": "available", "label": "资金流"}, "deepseek_called": False}

        auto_hydrate.execute_auto_hydrate(
            state,
            target="002008",
            market_type="A股",
            module_specs=_specs(),
            handlers={"moneyflow": handler},
            ttl_seconds=600,
            now_ts=1000,
        )
        packet = auto_hydrate.execute_auto_hydrate(
            state,
            target="002008",
            market_type="A股",
            module_specs=_specs(),
            handlers={"moneyflow": handler},
            ttl_seconds=600,
            now_ts=1100,
            force=True,
        )

        self.assertEqual(calls, ["002008", "002008"])
        self.assertTrue(packet["forced"])
        self.assertEqual(packet["decision"]["reason"], "force_refresh")

    def test_failure_preserves_cache_and_reports_failed(self):
        state = {
            "command_center_moneyflow_packet": {
                "status": "ready",
                "data_status": "ready",
                "updated_at": "2026-06-04T15:00:00",
            }
        }

        def handler(**kwargs):
            raise RuntimeError("network timeout")

        packet = auto_hydrate.execute_auto_hydrate(
            state,
            target="002008",
            market_type="A股",
            module_specs=_specs(),
            handlers={"moneyflow": handler},
            now_ts=1000,
        )

        module = packet["modules"][0]
        self.assertEqual(module["status"], "failed")
        self.assertTrue(module["cache_available"])
        self.assertIn("保留上次缓存", module["conclusion"])
        self.assertEqual(state["legacy_moneyflow_packet"]["status"], "ready")

    def test_missing_runtime_secret_is_not_reported_as_permission_denied(self):
        state = {}

        def handler(**kwargs):
            return {
                "item": {
                    "capability_state": "not_configured",
                    "error": "缺少 TUSHARE_TOKEN 配置",
                    "deepseek_called": False,
                },
                "deepseek_called": False,
            }

        packet = auto_hydrate.execute_auto_hydrate(
            state,
            target="002008",
            market_type="A股",
            module_specs=_specs(),
            handlers={"moneyflow": handler},
            now_ts=1000,
        )

        module = packet["modules"][0]
        self.assertEqual(module["status"], "skipped")
        self.assertEqual(module["status_label"], auto_hydrate.RUNTIME_SECRET_MISSING_HINT)
        self.assertTrue(module["runtime_secret_missing"])
        self.assertIn("App settings → Secrets", module["conclusion"])
        self.assertIn(".streamlit/secrets.toml", module["conclusion"])
        self.assertEqual(packet["summary"]["no_permission"], 0)
        self.assertEqual(packet["summary"]["skipped"], 1)
        self.assertFalse(packet["deepseek_called"])

    def test_main_summary_hides_diagnostic_terms(self):
        packet = auto_hydrate.build_status_packet(
            target="002008",
            market_type="A股",
            modules=[
                {
                    "key": "moneyflow",
                    "label": "资金流",
                    "status": "available",
                    "updated_at": "2026-06-05T09:30:00",
                }
            ],
            fingerprint="demo",
            hydrated=True,
            updated_at="2026-06-05T09:30:00",
        )
        summary = packet["summary_text"]

        for noisy in auto_hydrate.NOISY_DETAIL_TERMS:
            self.assertNotIn(noisy, summary)
        self.assertIn("A股专业数据", summary)

    def test_command_center_2_home_does_not_render_diagnostic_panels_before_return(self):
        source = Path("app.py").read_text(encoding="utf-8")
        function_start = source.index("def render_command_center_2_page")
        function_source = source[function_start:]
        main_path = function_source.split("\n    return", 1)[0]

        self.assertNotIn("render_a_share_data_capability_controls(", main_path)
        self.assertNotIn("render_home_a_share_diagnostic_recovery_controls(", main_path)
        self.assertNotIn("render_legacy_a_share_gap_recovery_panel(", main_path)

    def test_dragon_tiger_manual_check_uses_trade_date_adapter_contract(self):
        source = Path("app.py").read_text(encoding="utf-8")
        function_start = source.index("def _run_manual_dragon_tiger_capability_check")
        function_source = source[function_start:source.index("def _run_manual_moneyflow_capability_check", function_start)]

        self.assertIn('trade_date=request["end_date"]', function_source)
        self.assertNotIn('start_date=request["start_date"]', function_source)
        self.assertNotIn('end_date=request["end_date"]', function_source)

    def test_legacy_a_share_status_cards_are_collapsible_by_default(self):
        source = Path("app.py").read_text(encoding="utf-8")

        self.assertIn("cards_expanded=True", source)
        self.assertIn('with st.expander("查看接口状态卡 / 重新检测", expanded=False):', source)
        self.assertIn("cards_expanded=False", source)

    def test_legacy_tool_recovery_notice_defaults_to_collapsed_hint(self):
        source = Path("app.py").read_text(encoding="utf-8")
        function_start = source.index("def render_legacy_tool_recovery_notice_panel")
        function_source = source[function_start:source.index("def render_legacy_a_share_gap_recovery_panel", function_start)]

        self.assertIn('with st.expander(f"首页恢复提示｜{label}", expanded=False):', function_source)
        self.assertIn("不会自动运行扫描、回测或 DeepSeek", function_source)
        self.assertNotIn("_run_legacy_a_share_auto_hydrate(", function_source)


if __name__ == "__main__":
    unittest.main()
