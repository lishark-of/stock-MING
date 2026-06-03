import ast
import json
import unittest
from pathlib import Path

import market_data_capability as capability


class MarketDataCapabilityTests(unittest.TestCase):
    def test_permission_error_is_classified(self):
        item = capability.build_capability_item("limit_cpt_list", error="当前权限不足，需要 8000 积分")

        self.assertEqual(item["capability_state"], capability.STATE_PERMISSION_DENIED)
        self.assertEqual(item["status"], "权限不足")
        self.assertTrue(item["permission_likely"])
        self.assertTrue(item["should_skip_session"])

    def test_empty_recent_is_not_treated_as_failure(self):
        item = capability.build_capability_item("top_list", ok=True, rows=0)

        self.assertEqual(item["capability_state"], capability.STATE_EMPTY_RECENT)
        self.assertEqual(item["status"], "近期无数据")
        self.assertIn("非交易日", item["action_hint"])

    def test_missing_token_is_not_configuration_not_permission(self):
        item = capability.build_capability_item("daily", error="缺少 TUSHARE_TOKEN 配置")

        self.assertEqual(item["capability_state"], capability.STATE_NOT_CONFIGURED)
        self.assertEqual(item["status"], "未配置")
        self.assertFalse(item["permission_likely"])

    def test_cached_and_session_skipped_states_are_explicit(self):
        cached = capability.build_capability_item("moneyflow", ok=True, rows=12, cached=True)
        skipped = capability.build_capability_item("limit_cpt_list", error="limit_cpt_list 当前权限不足，已在本会话跳过重复请求。")

        self.assertEqual(cached["capability_state"], capability.STATE_STALE_CACHE)
        self.assertEqual(cached["status"], "使用缓存")
        self.assertEqual(skipped["capability_state"], capability.STATE_DISABLED_THIS_SESSION)
        self.assertEqual(skipped["status"], "本会话跳过")

    def test_requires_manual_refresh_state(self):
        item = capability.build_capability_item("margin_detail", requires_manual_refresh=True)

        self.assertEqual(item["capability_state"], capability.STATE_REQUIRES_MANUAL_REFRESH)
        self.assertEqual(item["status"], "需要手动刷新")
        self.assertIn("页面打开不自动调用", item["action_hint"])

    def test_summarize_tushare_result_handles_dict_rows(self):
        result = {"ok": True, "rows": 5, "latest_date": "20260602", "source": "Tushare"}
        item = capability.summarize_tushare_result("moneyflow", result=result, latency_ms=23)

        self.assertEqual(item["capability_state"], capability.STATE_AVAILABLE)
        self.assertEqual(item["rows"], 5)
        self.assertEqual(item["latest_date"], "20260602")
        self.assertEqual(item["latency_ms"], 23)

    def test_packet_summary_counts_key_states(self):
        items = [
            capability.build_capability_item("daily", ok=True, rows=10),
            capability.build_capability_item("limit_cpt_list", error="权限不足"),
            capability.build_capability_item("top_list", ok=True, rows=0),
            capability.build_capability_item("moneyflow", ok=True, rows=3, cached=True),
        ]
        packet = capability.build_tushare_capability_packet(items, checked_at="2026-06-02T21:30:00")

        self.assertEqual(packet["ok_count"], 1)
        self.assertEqual(packet["permission_denied_count"], 1)
        self.assertEqual(packet["empty_count"], 1)
        self.assertEqual(packet["cache_count"], 1)
        self.assertFalse(packet["deepseek_called"])
        json.dumps(packet, ensure_ascii=False)

    def test_professional_fact_packet_distinguishes_legacy_a_share_states(self):
        packet = capability.build_a_share_professional_capability_packet(
            {
                "stock_code": "002008",
                "dragon_tiger": {
                    "available": False,
                    "api": "top_list/top_inst",
                    "message": "近30日未见龙虎榜上榜记录",
                    "updated_at": "2026-06-02T21:30:00",
                },
                "margin": {
                    "available": False,
                    "api": "margin_detail",
                    "error": "抱歉，您没有访问该接口的权限",
                    "updated_at": "2026-06-02T21:30:00",
                },
                "moneyflow": {
                    "available": True,
                    "api": "moneyflow",
                    "date": "20260602",
                    "updated_at": "2026-06-02T21:30:00",
                },
                "limit_emotion": {
                    "available": False,
                    "api": "stk_limit / limit_list_d / limit_cpt_list",
                    "warning": "limit_cpt_list 当前权限不足，已在本会话跳过重复请求。",
                    "updated_at": "2026-06-02T21:30:00",
                },
                "chip_radar": {
                    "available": False,
                    "api": "cyq_perf/cyq_chips",
                    "message": "暂未取得可验证筹码/胜率数据，可能为数据尚未更新、接口权限不足或标的暂不覆盖。",
                    "updated_at": "2026-06-02T21:30:00",
                },
            }
        )
        by_section = {item["section"]: item for item in packet["items"]}

        self.assertEqual(by_section["dragon_tiger"]["capability_state"], capability.STATE_EMPTY_RECENT)
        self.assertEqual(by_section["margin"]["capability_state"], capability.STATE_PERMISSION_DENIED)
        self.assertEqual(by_section["moneyflow"]["capability_state"], capability.STATE_AVAILABLE)
        self.assertEqual(by_section["limit_emotion"]["capability_state"], capability.STATE_DISABLED_THIS_SESSION)
        self.assertEqual(by_section["chip_radar"]["capability_state"], capability.STATE_EMPTY_RECENT)
        self.assertEqual(by_section["hard_risk.announcements"]["capability_state"], capability.STATE_EMPTY_RECENT)
        self.assertEqual(by_section["hard_risk.pledge"]["capability_state"], capability.STATE_EMPTY_RECENT)
        self.assertFalse(packet["deepseek_called"])
        json.dumps(packet, ensure_ascii=False)

    def test_professional_fact_packet_includes_hard_risk_capability_states(self):
        packet = capability.build_a_share_professional_capability_packet(
            {
                "stock_code": "002008",
                "moneyflow": {"available": True, "api": "moneyflow", "date": "20260602"},
                "verified_hard_risks": {
                    "announcements": {
                        "available": True,
                        "source": "Tushare",
                        "api": "anns_d",
                        "rows": [{"ann_date": "20260602", "title": "关于股东减持计划的公告"}],
                        "updated_at": "2026-06-02T21:30:00",
                    },
                    "holder_reduction": {
                        "available": False,
                        "source": "Tushare",
                        "api": "stk_holdertrade",
                        "message": "近180天未取得股东减持记录",
                        "updated_at": "2026-06-02T21:30:00",
                    },
                    "pledge": {
                        "available": False,
                        "source": "Tushare",
                        "api": "pledge_stat/pledge_detail",
                        "error": "抱歉，您没有访问该接口的权限",
                        "updated_at": "2026-06-02T21:30:00",
                    },
                },
            }
        )
        by_section = {item["section"]: item for item in packet["items"]}

        self.assertEqual(by_section["hard_risk.announcements"]["capability_state"], capability.STATE_AVAILABLE)
        self.assertEqual(by_section["hard_risk.announcements"]["latest_date"], "20260602")
        self.assertEqual(by_section["hard_risk.holder_reduction"]["capability_state"], capability.STATE_EMPTY_RECENT)
        self.assertEqual(by_section["hard_risk.pledge"]["capability_state"], capability.STATE_PERMISSION_DENIED)
        self.assertIn("检查 Tushare", by_section["hard_risk.pledge"]["action_hint"])
        self.assertFalse(packet["deepseek_called"])
        json.dumps(packet, ensure_ascii=False)

    def test_supabase_capability_packet_normalizes_table_status(self):
        packet = capability.build_supabase_capability_packet(
            {
                "checked_at": "2026-06-02T22:00:00",
                "items": [
                    {"table": "brain_memory", "ok": True, "rows": 1, "latency_ms": 12, "status": "正常"},
                    {"table": "market_news", "ok": False, "rows": 0, "error": "Supabase 未配置或初始化失败"},
                ],
            }
        )
        by_api = {item["api"]: item for item in packet["items"]}

        self.assertEqual(packet["source"], "Supabase")
        self.assertEqual(by_api["brain_memory"]["provider"], "Supabase")
        self.assertEqual(by_api["brain_memory"]["capability_state"], capability.STATE_AVAILABLE)
        self.assertEqual(by_api["market_news"]["capability_state"], capability.STATE_NOT_CONFIGURED)
        self.assertFalse(packet["deepseek_called"])
        json.dumps(packet, ensure_ascii=False)

    def test_unified_provider_packet_combines_data_sources_and_manual_placeholders(self):
        a_share_packet = capability.build_a_share_professional_capability_packet(
            {
                "stock_code": "002008",
                "moneyflow": {"available": True, "api": "moneyflow", "date": "20260602"},
                "margin": {"available": False, "error": "权限不足"},
            },
            checked_at="2026-06-02T22:05:00",
        )
        health_result = {
            "checked_at": "2026-06-02T22:06:00",
            "supabase": {
                "source": "Supabase",
                "items": [
                    {"table": "brain_memory", "ok": True, "rows": 1},
                ],
            },
        }

        packet = capability.build_unified_provider_capability_packet(
            health_result=health_result,
            a_share_packet=a_share_packet,
            include_manual_providers=True,
        )
        providers = {item["provider"] for item in packet["items"]}
        labels = {item["label"] for item in packet["items"]}

        self.assertEqual(packet["source"], capability.SOURCE_UNIFIED)
        self.assertIn("Tushare", providers)
        self.assertIn("Supabase", providers)
        self.assertIn("AkShare", providers)
        self.assertIn("yfinance", providers)
        self.assertIn("AkShare 重型刷新", labels)
        self.assertIn("yfinance 行情/新闻", labels)
        self.assertGreaterEqual(packet["providers"]["Tushare"]["total"], 1)
        self.assertFalse(packet["deepseek_called"])
        json.dumps(packet, ensure_ascii=False)

    def test_forbidden_imports(self):
        tree = ast.parse(Path("market_data_capability.py").read_text(encoding="utf-8"))
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module or "")

        forbidden = {
            "streamlit",
            "app",
            "tushare_adapter",
            "tushare",
            "akshare",
            "yfinance",
            "data_fetcher",
            "backtester",
            "openai",
        }
        self.assertTrue(forbidden.isdisjoint(set(imports)))


if __name__ == "__main__":
    unittest.main()
