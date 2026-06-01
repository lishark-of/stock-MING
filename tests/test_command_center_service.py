import unittest
import datetime

import command_center_service as service


class CommandCenterServiceTests(unittest.TestCase):
    def test_build_live_packet_only_reads_section_builders(self):
        state = {}
        calls = {"builder": 0, "refresh": 0}

        def section_builder():
            calls["builder"] += 1
            return {
                "status": "未刷新",
                "summary": "只读缓存",
                "is_fresh": False,
            }

        def refresh_handler():
            calls["refresh"] += 1
            return {"status": "ok"}

        packet = service.build_live_packet(state, {"market": section_builder})

        self.assertEqual(calls, {"builder": 1, "refresh": 0})
        self.assertEqual(packet["market"]["summary"], "只读缓存")
        self.assertEqual(packet["errors"], [])
        self.assertEqual(packet["market"]["refresh_level"], service.REFRESH_LEVEL_AUTO_LIGHT)
        self.assertFalse(packet["market"]["deepseek_called"])
        self.assertFalse(packet["conclusion"]["deepseek_called"])
        self.assertFalse(state["command_center_live_packet"]["market"]["deepseek_called"])
        self.assertTrue(refresh_handler)

    def test_safe_refresh_module_defaults_to_manual_basic(self):
        state = {}
        result = service.safe_refresh_module(
            state,
            "market",
            "市场环境",
            lambda: {"status": "ok", "summary": "today"},
        )

        self.assertEqual(result["refresh_level"], service.REFRESH_LEVEL_MANUAL_BASIC)
        self.assertEqual(result["last_success"]["refresh_level"], service.REFRESH_LEVEL_MANUAL_BASIC)
        self.assertFalse(result["deepseek_called"])

    def test_auto_light_build_does_not_call_refresh_handler(self):
        state = {}
        calls = {"builder": 0, "refresh": 0}

        def builder():
            calls["builder"] += 1
            return {"status": "已刷新", "summary": "local only", "is_fresh": True}

        def refresh_handler():
            calls["refresh"] += 1
            return {"status": "ok"}

        packet = service.build_live_packet(
            state,
            {"market": builder},
            refresh_level=service.REFRESH_LEVEL_AUTO_LIGHT,
        )

        self.assertEqual(calls, {"builder": 1, "refresh": 0})
        self.assertEqual(packet["market"]["refresh_level"], service.REFRESH_LEVEL_AUTO_LIGHT)
        self.assertEqual(packet["market"]["refresh_label"], "实时轻量")
        self.assertTrue(refresh_handler)

    def test_safe_refresh_module_preserves_last_success_on_failure(self):
        state = {}

        def ok_handler():
            return {
                "status": "ok",
                "updated_at": "2026-05-31T10:00:00",
                "source": "unit",
                "summary": "fresh data",
                "value": 7,
            }

        first = service.safe_refresh_module(state, "market", "市场环境", ok_handler)

        def fail_handler():
            raise RuntimeError("upstream down")

        second = service.safe_refresh_module(state, "market", "市场环境", fail_handler)
        record = service.get_module_record(state, "market")
        packet = service.build_live_packet(
            state,
            {"market": lambda: {"status": "已刷新", "summary": "cached section"}},
        )

        self.assertTrue(first["ok"])
        self.assertFalse(second["ok"])
        self.assertTrue(second["stale"])
        self.assertEqual(second["last_error"], "upstream down")
        self.assertEqual(second["last_success"]["summary"], "fresh data")
        self.assertEqual(second["refresh_level"], service.REFRESH_LEVEL_MANUAL_BASIC)
        self.assertEqual(second["last_success"]["refresh_level"], service.REFRESH_LEVEL_MANUAL_BASIC)
        self.assertEqual(second["data"]["value"], 7)
        self.assertEqual(record["last_success"]["data"]["value"], 7)
        self.assertEqual(service.get_module_meta(state, "market")["status"], "失败")
        self.assertEqual(len(packet["errors"]), 1)
        self.assertEqual(packet["errors"][0]["module"], "市场环境")
        self.assertEqual(packet["errors"][0]["message"], "upstream down")
        self.assertIn("updated_at", packet["errors"][0])
        self.assertEqual(packet["errors"][0]["source"], "unit")

    def test_safe_refresh_module_treats_failed_status_as_failure(self):
        state = {}

        service.safe_refresh_module(
            state,
            "next_ticket",
            "下一票雷达",
            lambda: {"status": "ok", "summary": "previous", "value": 3},
        )

        result = service.safe_refresh_module(
            state,
            "next_ticket",
            "下一票雷达",
            lambda: {"status": "failed", "error": "scan failed", "value": 0},
        )
        packet = service.build_live_packet(state, {"next_ticket": lambda: {}})

        self.assertFalse(result["ok"])
        self.assertTrue(result["stale"])
        self.assertEqual(result["last_success"]["data"]["value"], 3)
        self.assertEqual(result["data"]["value"], 3)
        self.assertEqual(result["refresh_level"], service.REFRESH_LEVEL_MANUAL_BASIC)
        self.assertEqual(packet["errors"][0]["message"], "scan failed")
        self.assertFalse(packet["next_ticket"]["deepseek_called"])

    def test_module_section_fields_are_normalized(self):
        state = {}
        packet = service.build_live_packet(state, {"quant": lambda: {}})
        section = packet["quant"]

        for key in (
            "status",
            "updated_at",
            "source",
            "summary",
            "data",
            "last_success",
            "last_error",
            "stale",
            "refresh_level",
            "refresh_label",
            "deepseek_called",
        ):
            self.assertIn(key, section)

        self.assertEqual(section["status"], "未刷新")
        self.assertEqual(section["last_error"], "")
        self.assertFalse(section["stale"])
        self.assertEqual(section["refresh_level"], service.REFRESH_LEVEL_AUTO_LIGHT)
        self.assertFalse(section["deepseek_called"])

    def test_run_refresh_sequence_returns_structured_errors(self):
        def runner(module_key, label):
            del module_key
            return {
                "ok": False,
                "module": label,
                "last_error": "boom",
                "updated_at": "2026-05-31T11:00:00",
                "source": "unit-source",
                "deepseek_called": False,
            }

        summary = service.run_refresh_sequence(
            [("market", "市场环境", lambda: {})],
            runner,
        )

        self.assertFalse(summary["deepseek_called"])
        self.assertEqual(summary["errors"], [
            {
                "module": "市场环境",
                "message": "boom",
                "updated_at": "2026-05-31T11:00:00",
                "source": "unit-source",
            }
        ])

    def test_get_refresh_label_outputs_expected_states(self):
        today = datetime.datetime.now().isoformat(timespec="seconds")
        yesterday = (datetime.datetime.now() - datetime.timedelta(days=1)).isoformat(timespec="seconds")

        self.assertEqual(
            service.get_refresh_label({
                "refresh_level": service.REFRESH_LEVEL_AUTO_LIGHT,
                "updated_at": today,
                "is_fresh": True,
                "stale": False,
            }),
            "实时轻量",
        )
        self.assertEqual(
            service.get_refresh_label({
                "refresh_level": service.REFRESH_LEVEL_MANUAL_BASIC,
                "updated_at": today,
                "is_fresh": True,
            }),
            "今日已刷新",
        )
        self.assertEqual(
            service.get_refresh_label({
                "refresh_level": service.REFRESH_LEVEL_MANUAL_BASIC,
                "updated_at": yesterday,
                "last_success": {"updated_at": yesterday},
            }),
            "使用缓存",
        )
        self.assertEqual(
            service.get_refresh_label({
                "refresh_level": service.REFRESH_LEVEL_AUTO_LIGHT,
                "status": "未刷新",
                "summary": "missing",
            }),
            "需要深度刷新",
        )

    def test_failed_status_with_last_success_label_uses_cache(self):
        state = {}
        service.safe_refresh_module(
            state,
            "market",
            "市场环境",
            lambda: {"status": "ok", "summary": "previous", "updated_at": "2026-05-31T10:00:00"},
        )
        service.safe_refresh_module(
            state,
            "market",
            "市场环境",
            lambda: {"status": "failed", "error": "down"},
        )

        packet = service.build_live_packet(state, {"market": lambda: {}})

        self.assertEqual(packet["market"]["refresh_label"], "使用缓存")
        self.assertEqual(packet["market"]["summary"], "previous")
        self.assertEqual(packet["errors"][0]["message"], "down")


if __name__ == "__main__":
    unittest.main()
