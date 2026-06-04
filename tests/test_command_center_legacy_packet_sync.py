import ast
import json
import unittest
from pathlib import Path

import command_center_legacy_packet_sync as sync


class CommandCenterLegacyPacketSyncTests(unittest.TestCase):
    def test_quant_sync_prefers_latest_legacy_result_over_existing_packet(self):
        packet = sync.sync_legacy_quant_packet(
            {
                "command_center_quant_packet": {
                    "status": "ready",
                    "score": 10,
                    "summary": "旧 packet",
                    "target": "002008.SZ",
                },
                "legacy_quant_result": {
                    "status": "completed",
                    "generated_at": "2026-06-03T10:00:00",
                    "target": "002008.SZ",
                    "market_type": "A股",
                    "score": 68,
                    "direction": "偏积极但需验证",
                    "summary": "最新旧版量化结果。",
                },
            },
            target="002008.SZ",
        )

        self.assertEqual(packet["status"], "ready")
        self.assertEqual(packet["score"], 68)
        self.assertEqual(packet["summary"], "最新旧版量化结果。")
        self.assertEqual(packet["data_status"], "ready")
        self.assertFalse(packet["deepseek_called"])
        json.dumps(packet, ensure_ascii=False)

    def test_discipline_sync_prefers_latest_backtest_over_existing_packet(self):
        packet = sync.sync_legacy_discipline_packet(
            {
                "command_center_discipline_packet": {
                    "status": "ready",
                    "summary": "旧纪律 packet",
                    "win_rate": 12,
                    "target": "002008.SZ",
                },
                "last_backtest_report": {
                    "ticker": "002008.SZ",
                    "summary": "最新回测缓存已生成。",
                    "source": "yfinance",
                    "date_range": {"start": "2025-01-01", "end": "2026-06-03"},
                    "metrics": {"win_rate": 62, "max_drawdown": -12, "sharpe": 1.1, "trade_count": 18},
                    "latest_signal": {"action": "继续观察", "reason": "趋势未破坏。"},
                },
                "last_multi_backtest": {"summary": "多模式整体稳定。"},
            },
            target="002008.SZ",
        )

        self.assertEqual(packet["status"], "ready")
        self.assertEqual(packet["summary"], "最新回测缓存已生成。")
        self.assertEqual(packet["win_rate"], 62)
        self.assertEqual(packet["data_status"], "ready")
        self.assertEqual(packet["updated_at"], "2026-06-03")
        self.assertFalse(packet["deepseek_called"])
        json.dumps(packet, ensure_ascii=False)

    def test_etf_sync_prefers_latest_allocation_over_existing_packet(self):
        packet = sync.sync_legacy_etf_packet(
            {
                "command_center_etf_packet": {
                    "status": "ready",
                    "recommended_etfs": [{"code": "OLD", "name": "旧 ETF"}],
                    "source": "旧 packet",
                },
                "legacy_margin_etf_allocation_result": {
                    "status": "completed",
                    "generated_at": "2026-06-03T10:00:00",
                    "recommended_margin_ratio": 12,
                    "recommended_cash_ratio": 35,
                    "today_main_direction": "半导体回踩确认",
                    "recommended_etfs": [
                        {
                            "code": "560780.SH",
                            "name": "半导体 ETF",
                            "bucket": "科技成长ETF",
                            "score": 78,
                            "action_state": "可小幅配置",
                            "trigger_condition": "回踩不破 MA20 且成交额放大。",
                        }
                    ],
                    "summary": "最新融资 ETF 配置结果。",
                },
                "legacy_margin_etf_daily_packet": {
                    "updated_at": "2026-06-03T10:00:00",
                    "source": "融资 ETF 本地配置快照",
                    "daily_dataset": {"status": "manual_basic_local_config"},
                },
            },
            live_packet={"margin_etf": {"updated_at": "2026-06-03T10:00:00"}},
        )

        self.assertEqual(packet["status"], "ready")
        self.assertEqual(packet["recommended_etfs"][0]["code"], "560780.SH")
        self.assertEqual(packet["recommended_etfs"][0]["name"], "半导体 ETF")
        self.assertEqual(packet["today_main_direction"], "半导体回踩确认")
        self.assertEqual(packet["data_status"], "ready")
        self.assertFalse(packet["deepseek_called"])
        json.dumps(packet, ensure_ascii=False)

    def test_radar_sync_prefers_latest_scan_over_existing_packet(self):
        packet = sync.sync_legacy_radar_packet(
            {
                "command_center_radar_packet": {
                    "status": "ready",
                    "top_candidates": [{"ticker": "OLD", "name": "旧候选"}],
                    "source": "旧 packet",
                },
                "radar_scan_results": {
                    "generated_at": "2026-06-03T10:00:00",
                    "status": "completed",
                    "summary": {
                        "source_mode": "下一票雷达本地缓存",
                        "deepseek_called": False,
                    },
                    "rule_rows": [
                        {
                            "candidate": {"ticker": "002008.SZ", "name": "大族激光"},
                            "score": {
                                "total_score": 81,
                                "battle_state": "可准备",
                                "trigger_conditions": ["放量站稳 MA20"],
                                "invalid_conditions": ["跌破 MA20"],
                            },
                        }
                    ],
                },
                "radar_scan_summary": {
                    "source_mode": "下一票雷达本地缓存",
                    "deepseek_called": False,
                },
                "radar_scan_status": "completed",
                "radar_scan_finished_at": "2026-06-03T10:00:00",
            },
            live_packet={"next_ticket": {"updated_at": "2026-06-03T10:00:00"}},
        )

        self.assertEqual(packet["status"], "ready")
        self.assertEqual(packet["top_candidates"][0]["ticker"], "002008.SZ")
        self.assertEqual(packet["top_candidates"][0]["name"], "大族激光")
        self.assertEqual(packet["top_candidates"][0]["status_label"], "可准备")
        self.assertEqual(packet["data_status"], "ready")
        self.assertFalse(packet["deepseek_called"])
        json.dumps(packet, ensure_ascii=False)

    def test_extract_legacy_radar_rows_accepts_common_cache_shapes_without_mutation(self):
        state = {
            "radar_scan_results": {
                "generated_at": "2026-06-03T10:00:00",
                "top_candidates": [
                    {"ticker": "300750.SZ", "name": "宁德时代", "action_state": "等验证"},
                    {"ticker": "512480.SH", "name": "半导体 ETF", "action_state": "只观察"},
                ],
            },
            "radar_scan_summary": {
                "candidates": [{"ticker": "OLD", "name": "旧候选"}],
            },
            "command_center_radar_packet": {
                "top_candidates": [{"ticker": "PKT", "name": "旧 packet"}],
            },
        }
        before = json.dumps(state, ensure_ascii=False, sort_keys=True)

        rows = sync.extract_legacy_radar_rows(state)

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["ticker"], "300750.SZ")
        self.assertEqual(rows[1]["ticker"], "512480.SH")
        self.assertEqual(json.dumps(state, ensure_ascii=False, sort_keys=True), before)

    def test_radar_sync_accepts_top_candidates_cache_shape(self):
        packet = sync.sync_legacy_radar_packet(
            {
                "radar_scan_results": {
                    "generated_at": "2026-06-03T10:00:00",
                    "status": "completed",
                    "top_candidates": [
                        {
                            "ticker": "300750.SZ",
                            "name": "宁德时代",
                            "score": 82,
                            "action_state": "等验证",
                            "trigger_condition": "放量站稳 MA20",
                            "invalidation_condition": "跌破 MA20",
                        },
                    ],
                },
                "radar_scan_summary": {
                    "source_mode": "下一票雷达本地缓存",
                    "deepseek_called": False,
                },
            },
            live_packet={"next_ticket": {"updated_at": "2026-06-03T10:00:00"}},
        )

        self.assertEqual(packet["status"], "ready")
        self.assertEqual(packet["top_candidates"][0]["ticker"], "300750.SZ")
        self.assertEqual(packet["top_candidates"][0]["status_label"], "等验证")
        self.assertEqual(packet["top_candidates"][0]["trigger_condition"], "放量站稳 MA20")
        self.assertEqual(packet["data_status"], "ready")
        self.assertFalse(packet["deepseek_called"])
        json.dumps(packet, ensure_ascii=False)

    def test_sync_helpers_do_not_mutate_input_state(self):
        state = {
            "command_center_quant_packet": {"status": "ready", "score": 10},
            "legacy_quant_result": {"status": "completed", "score": 70},
        }
        before = json.dumps(state, ensure_ascii=False, sort_keys=True)

        sync.sync_legacy_quant_packet(state)

        after = json.dumps(state, ensure_ascii=False, sort_keys=True)
        self.assertEqual(after, before)

    def test_forbidden_imports(self):
        tree = ast.parse(Path("command_center_legacy_packet_sync.py").read_text(encoding="utf-8"))
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module or "")

        forbidden = {
            "streamlit",
            "app",
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
