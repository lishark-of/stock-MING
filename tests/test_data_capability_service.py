import ast
import json
import unittest
from pathlib import Path

import data_capability_registry as registry
import data_capability_service as service


class DataCapabilityServiceTests(unittest.TestCase):
    def test_registry_contains_required_capabilities_and_schema(self):
        payload = registry.build_initial_capability_registry(target="002008.SZ", market_type="A_SHARE")
        items = payload["items"]
        names = {item["name"] for item in items}
        providers = {item["provider"] for item in items}
        required_fields = {
            "name",
            "provider",
            "market",
            "tier",
            "status",
            "last_success_at",
            "last_error",
            "used_in_decision",
            "requires_user_action",
            "description",
        }
        expected_names = {
            "Tushare 日线/行情",
            "Tushare 个股资金流",
            "Tushare 龙虎榜",
            "Tushare 融资融券",
            "Tushare 公告",
            "Tushare 涨跌停",
            "Tushare 指数成分/权重",
            "Tushare 筹码/胜率",
            "AkShare 个股资金",
            "AkShare 概念",
            "AkShare 行业",
            "AkShare 盘口/补充数据",
            "yfinance 行情",
            "yfinance 财报/基本面",
            "yfinance 行业/宏观代理",
            "Supabase 记忆",
            "Supabase 投喂",
            "Supabase 历史记录",
            "Supabase 回测缓存",
            "Home Snapshot",
            "DeepSeek 解释",
        }
        valid_statuses = {
            registry.STATUS_UNKNOWN,
            registry.STATUS_AVAILABLE,
            registry.STATUS_FAILED,
            registry.STATUS_NO_PERMISSION,
            registry.STATUS_NO_DATA,
            registry.STATUS_CACHED,
            registry.STATUS_SKIPPED,
        }

        self.assertTrue(expected_names.issubset(names))
        self.assertTrue({"Tushare", "AkShare", "yfinance", "Supabase", "Home Snapshot", "DeepSeek"}.issubset(providers))
        for item in items:
            self.assertTrue(required_fields.issubset(item), item)
            self.assertIn(item["status"], valid_statuses)
            self.assertTrue(item["description"])
        deepseek = next(item for item in items if item["name"] == "DeepSeek 解释")
        self.assertTrue(deepseek["requires_user_action"])
        self.assertFalse(deepseek["used_in_decision"])
        json.dumps(payload, ensure_ascii=False)

    def test_market_scope_skips_wrong_market_capabilities(self):
        us_payload = registry.build_initial_capability_registry(target="AAPL", market_type="US")
        us_by_name = {item["name"]: item for item in us_payload["items"]}
        etf_payload = registry.build_initial_capability_registry(target="560780.SH")
        etf_by_name = {item["name"]: item for item in etf_payload["items"]}

        self.assertEqual(us_by_name["Tushare 个股资金流"]["status"], registry.STATUS_SKIPPED)
        self.assertEqual(us_by_name["Tushare 涨跌停"]["status"], registry.STATUS_SKIPPED)
        self.assertEqual(us_by_name["yfinance 行情"]["status"], registry.STATUS_UNKNOWN)
        self.assertEqual(us_by_name["yfinance 财报/基本面"]["status"], registry.STATUS_UNKNOWN)
        self.assertEqual(etf_by_name["Tushare ETF"]["status"], registry.STATUS_UNKNOWN)
        self.assertEqual(etf_by_name["Tushare 个股资金流"]["status"], registry.STATUS_SKIPPED)

    def test_diagnose_capability_runs_probe_only_when_called(self):
        payload = registry.build_initial_capability_registry(target="002008.SZ", market_type="A_SHARE")
        calls = {"count": 0}

        def probe():
            calls["count"] += 1
            return {
                "ok": True,
                "updated_at": "2026-06-05T09:30:00",
                "latency_ms": 42,
                "used_in_decision": True,
            }

        self.assertEqual(calls["count"], 0)
        updated = service.diagnose_capability(payload, "Tushare 日线/行情", probe)
        by_name = {item["name"]: item for item in updated["items"]}

        self.assertEqual(calls["count"], 1)
        self.assertEqual(by_name["Tushare 日线/行情"]["status"], registry.STATUS_AVAILABLE)
        self.assertEqual(by_name["Tushare 日线/行情"]["last_success_at"], "2026-06-05T09:30:00")
        self.assertEqual(by_name["Tushare 日线/行情"]["latency_ms"], 42)
        self.assertTrue(by_name["Tushare 日线/行情"]["used_in_decision"])

    def test_diagnose_capability_records_probe_exception(self):
        payload = registry.build_initial_capability_registry(target="002008.SZ", market_type="A_SHARE")

        def probe():
            raise RuntimeError("Tushare timeout")

        updated = service.diagnose_capability(payload, "Tushare 个股资金流", probe)
        by_name = {item["name"]: item for item in updated["items"]}

        self.assertEqual(by_name["Tushare 个股资金流"]["status"], registry.STATUS_FAILED)
        self.assertIn("Tushare timeout", by_name["Tushare 个股资金流"]["last_error"])

    def test_basic_refresh_probe_maps_provider_statuses_without_model_call(self):
        payload = registry.build_initial_capability_registry(target="002008.SZ", market_type="A_SHARE")
        health_result = {
            "tushare": {
                "items": [
                    {"api": "moneyflow", "ok": True, "latest_date": "20260605"},
                    {"api": "margin_detail", "capability_state": "permission_denied", "error": "权限不足"},
                    {"api": "limit_cpt_list", "capability_state": "empty_recent"},
                    {"api": "cyq_perf", "cached": True, "updated_at": "2026-06-04T15:00:00"},
                ]
            }
        }
        yfinance_snapshot = {"price": 123.4, "raw_source": "yfinance", "data_date": "2026-06-05"}
        akshare_snapshot = {
            "source_status": {
                "individual_fund_flow_primary": {"used": True, "error": "permission denied"},
                "individual_fund_flow_fallback": {},
            },
            "warnings": ["permission denied"],
        }
        supabase_result = {
            "supabase": {
                "items": [
                    {"table": "brain_memory", "ok": True, "updated_at": "2026-06-05T09:00:00"},
                    {"table": "trade_history", "ok": True, "updated_at": "2026-06-05T09:01:00"},
                    {"table": "backtest_cache", "capability_state": "stale_cache", "updated_at": "2026-06-04T16:00:00"},
                ]
            }
        }
        home_snapshot = {
            "generated_at": "2026-06-05T09:10:00",
            "data_freshness": {"state": "today"},
        }

        updated, packet = service.apply_basic_refresh_capability_probe(
            payload,
            health_result,
            yfinance_snapshot,
            akshare_snapshot,
            supabase_result,
            deepseek_configured=False,
            deepseek_key_count=0,
            home_snapshot=home_snapshot,
            market_type="A_SHARE",
        )
        by_name = {item["name"]: item for item in updated["items"]}

        self.assertEqual(by_name["Tushare 个股资金流"]["status"], registry.STATUS_AVAILABLE)
        self.assertEqual(by_name["Tushare 融资融券"]["status"], registry.STATUS_NO_PERMISSION)
        self.assertEqual(by_name["Tushare 涨跌停"]["status"], registry.STATUS_NO_DATA)
        self.assertEqual(by_name["Tushare 筹码/胜率"]["status"], registry.STATUS_CACHED)
        self.assertEqual(by_name["yfinance 行情"]["status"], registry.STATUS_AVAILABLE)
        self.assertEqual(by_name["AkShare 个股资金"]["status"], registry.STATUS_NO_PERMISSION)
        self.assertEqual(by_name["Supabase 记忆"]["status"], registry.STATUS_AVAILABLE)
        self.assertEqual(by_name["Supabase 历史记录"]["status"], registry.STATUS_AVAILABLE)
        self.assertEqual(by_name["Supabase 回测缓存"]["status"], registry.STATUS_CACHED)
        self.assertEqual(by_name["Home Snapshot"]["status"], registry.STATUS_AVAILABLE)
        self.assertEqual(by_name["DeepSeek 解释"]["status"], registry.STATUS_NO_PERMISSION)
        self.assertIn("DeepSeek 未配置", by_name["DeepSeek 解释"]["last_error"])
        self.assertEqual(packet["registry_version"], "mvp_v1")
        self.assertTrue(packet["items"])
        json.dumps(packet, ensure_ascii=False)

    def test_no_data_status_maps_to_legacy_empty_recent(self):
        payload = registry.build_initial_capability_registry(target="002008.SZ", market_type="A_SHARE")
        updated = registry.update_capability_status(
            payload,
            "Tushare 涨跌停",
            registry.STATUS_NO_DATA,
            last_error="最近交易日暂无涨跌停记录",
        )
        packet = service.build_data_capability_packet(updated)
        row = next(item for item in packet["items"] if item["name"] == "Tushare 涨跌停")

        self.assertEqual(row["status"], "最近交易日暂无涨跌停记录")
        self.assertIn("近期无数据", row["capability_label"])
        self.assertEqual(row["last_error"], "最近交易日暂无涨跌停记录")

    def test_registry_and_service_do_not_import_external_clients(self):
        forbidden = {
            "streamlit",
            "tushare",
            "akshare",
            "yfinance",
            "openai",
            "supabase",
            "deepseek",
            "app",
        }
        for filename in ["data_capability_registry.py", "data_capability_service.py"]:
            tree = ast.parse(Path(filename).read_text(encoding="utf-8"))
            imports = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports.extend(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom):
                    imports.append(node.module or "")
            self.assertFalse(forbidden.intersection(imports), (filename, imports))


if __name__ == "__main__":
    unittest.main()
