import json
import tempfile
import unittest
import datetime as _dt
from pathlib import Path

import command_center_home_snapshot as snapshot


class CommandCenterHomeSnapshotTests(unittest.TestCase):
    def test_missing_snapshot_returns_empty_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = snapshot.load_home_action_snapshot(base_dir=tmp)

        self.assertTrue(payload["is_empty"])
        self.assertEqual(payload["data_freshness"]["state"], "missing")
        self.assertIn("暂无可执行候选", payload["empty_message"])

    def test_save_and_load_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = snapshot.build_home_action_snapshot(
                {
                    "command_center_decision_packet": {
                        "status": "ready",
                        "overall_action": "只观察",
                        "updated_at": "2026-06-01T09:30:00",
                    }
                },
                target="002008",
                now="2026-06-01T09:30:00",
            )
            path = snapshot.save_home_action_snapshot(payload, base_dir=tmp)
            loaded = snapshot.load_home_action_snapshot(base_dir=tmp)

        self.assertEqual(path.name, snapshot.SNAPSHOT_FILENAME)
        self.assertEqual(loaded["today_action"]["overall_action"], "只观察")
        self.assertFalse(loaded["deepseek_called"])

    def test_snapshot_filters_secrets_and_prompts(self):
        payload = snapshot.build_home_action_snapshot(
            {
                "command_center_decision_packet": {
                    "overall_action": "等待",
                    "api_key": "secret-value",
                    "deepseek_prompt": "raw prompt",
                    "nested": {"access_token": "token-value", "safe": "ok"},
                }
            }
        )
        dumped = json.dumps(payload, ensure_ascii=False)

        self.assertNotIn("secret-value", dumped)
        self.assertNotIn("raw prompt", dumped)
        self.assertNotIn("token-value", dumped)
        self.assertIn("ok", dumped)

    def test_missing_fields_are_safe(self):
        payload = snapshot.build_home_action_snapshot(
            {
                "command_center_decision_packet": object(),
                "strategy_execution_packet": object(),
                "radar_scan_results": object(),
            },
            position_profile=object(),
        )

        self.assertIsInstance(payload, dict)
        json.dumps(payload, ensure_ascii=False)

    def test_data_freshness_today_stale_missing_and_partial_failed(self):
        self.assertEqual(snapshot.classify_data_freshness("2026-06-01T09:30:00", today="2026-06-01"), "today")
        self.assertEqual(snapshot.classify_data_freshness("2026-05-31T09:30:00", today="2026-06-01"), "stale")
        self.assertEqual(snapshot.classify_data_freshness("", today="2026-06-01"), "missing")
        self.assertEqual(
            snapshot.build_data_freshness("2026-06-01T09:30:00", [{"message": "timeout"}], today="2026-06-01")["state"],
            "partial_failed",
        )

    def test_next_ticket_candidates_extract_top_three(self):
        state = {
            "radar_scan_results": {
                "generated_at": "2026-06-01T10:00:00",
                "rule_rows": [
                    {"candidate": {"ticker": "A", "name": "Alpha"}, "score": {"total_score": 81, "battle_state": "可准备"}},
                    {"candidate": {"ticker": "B", "name": "Beta"}, "score": {"total_score": 72, "battle_state": "等验证"}},
                    {"candidate": {"ticker": "C", "name": "Gamma"}, "score": {"total_score": 61, "battle_state": "只观察"}},
                    {"candidate": {"ticker": "D", "name": "Delta"}, "score": {"total_score": 50, "battle_state": "暂不纳入"}},
                ],
            }
        }

        items = snapshot.extract_next_ticket_candidates(state)

        self.assertEqual(len(items), 3)
        self.assertEqual(items[0]["ticker"], "A")
        self.assertEqual(items[0]["action_state"], "可准备")

    def test_next_ticket_candidates_prefer_radar_packet(self):
        state = {
            "command_center_radar_packet": {
                "status": "ready",
                "top_candidates": [
                    {"ticker": "X", "name": "Xray", "action_state": "可准备"},
                    {"ticker": "Y", "name": "Yankee", "action_state": "等验证"},
                ],
            },
            "radar_scan_results": {
                "rule_rows": [
                    {"candidate": {"ticker": "OLD", "name": "Old"}, "score": {"total_score": 1, "battle_state": "暂不纳入"}},
                ],
            },
        }

        items = snapshot.extract_next_ticket_candidates(state)

        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["ticker"], "X")

    def test_home_snapshot_persists_radar_packet(self):
        today = _dt.date.today().isoformat()
        state = {
            "command_center_decision_packet": {
                "status": "ready",
                "overall_action": "等待",
                "updated_at": f"{today}T10:00:00",
            },
            "radar_scan_status": "completed",
            "radar_scan_results": {
                "generated_at": f"{today}T10:01:00",
                "rule_rows": [
                    {
                        "candidate": {"ticker": "300750.SZ", "name": "宁德时代"},
                        "score": {
                            "total_score": 82,
                            "battle_state": "等验证",
                            "trigger_conditions": ["放量站稳 MA20"],
                            "invalid_conditions": ["跌破 MA20"],
                        },
                    },
                ],
            },
        }

        payload = snapshot.build_home_action_snapshot(state, target="002008.SZ", now=f"{today}T10:02:00")

        self.assertEqual(payload["radar_packet"]["top_candidates"][0]["ticker"], "300750.SZ")
        self.assertEqual(payload["next_ticket_candidates"][0]["trigger_condition"], "放量站稳 MA20")
        self.assertFalse(payload["radar_packet"]["deepseek_called"])

    def test_home_snapshot_persists_etf_packet_and_uses_it_for_summary(self):
        today = _dt.date.today().isoformat()
        state = {
            "command_center_decision_packet": {
                "status": "ready",
                "overall_action": "只观察",
                "updated_at": f"{today}T10:00:00",
            },
            "command_center_etf_packet": {
                "status": "ready",
                "updated_at": f"{today}T10:02:00",
                "current_margin_ratio": 28,
                "recommended_margin_ratio": 20,
                "recommended_cash_ratio": 22,
                "today_main_direction": "半导体 / 防守",
                "recommended_etfs": [
                    {"code": "560780.SH", "name": "半导体设备ETF广发", "bucket": "科技成长ETF", "score": 74},
                    {"code": "518880.SH", "name": "黄金 ETF", "bucket": "防守ETF", "score": 66},
                ],
                "watch_not_chase": ["不追高 ETF"],
                "deepseek_called": False,
            },
        }

        payload = snapshot.build_home_action_snapshot(state, target="002008.SZ", now=f"{today}T10:03:00")

        self.assertEqual(payload["etf_packet"]["recommended_etfs"][0]["code"], "560780.SH")
        self.assertEqual(payload["margin_etf_summary"]["recommended_margin_ratio"], 20)
        self.assertEqual(payload["margin_etf_summary"]["recommended_etfs"][0]["name"], "半导体设备ETF广发")
        self.assertIn("不追高 ETF", payload["margin_etf_summary"]["watch_not_chase"])
        self.assertFalse(payload["etf_packet"]["deepseek_called"])

    def test_home_snapshot_persists_discipline_packet(self):
        today = _dt.date.today().isoformat()
        state = {
            "command_center_decision_packet": {
                "status": "ready",
                "overall_action": "只观察",
                "updated_at": f"{today}T10:00:00",
            },
            "last_backtest_report": {
                "ticker": "002008.SZ",
                "summary": "规则历史表现可参考。",
                "metrics": {
                    "round_trip_win_rate": 64,
                    "max_drawdown_pct": -11,
                    "trade_count": 10,
                },
                "latest_signal": {"action": "继续观察", "reason": "趋势待确认"},
                "date_range": {"end": today},
            },
        }

        payload = snapshot.build_home_action_snapshot(state, target="002008.SZ", now=f"{today}T10:05:00")

        self.assertEqual(payload["discipline_packet"]["status"], "ready")
        self.assertEqual(payload["discipline_packet"]["win_rate"], 64)
        self.assertEqual(payload["discipline_packet"]["max_drawdown"], 11)
        self.assertIn("不会自动跑回测", payload["discipline_packet"]["backtest_required_text"])
        self.assertFalse(payload["discipline_packet"]["deepseek_called"])

    def test_deepseek_defaults_to_not_called(self):
        payload = snapshot.build_home_action_snapshot({
            "command_center_decision_packet": {"overall_action": "等待"}
        })

        self.assertFalse(payload["deepseek_called"])
        self.assertFalse(payload["data_freshness"]["deepseek_called"])

    def test_snapshot_path_is_under_cache_dir(self):
        path = snapshot.get_home_snapshot_path("/tmp/stock-ming-test")

        self.assertEqual(path.parent.name, snapshot.CACHE_DIR_NAME)
        self.assertEqual(path.name, snapshot.SNAPSHOT_FILENAME)

    def test_real_holding_scenario_keeps_actionable_snapshot_without_price(self):
        today = _dt.date.today().isoformat()
        state = {
            "command_center_decision_packet": {
                "status": "ready",
                "overall_action": "只观察",
                "risk_level": "中",
                "market_bias": "震荡",
                "position_mode": "持仓观察",
                "margin_mode": "不使用融资",
                "updated_at": f"{today}T09:30:00",
                "data_coverage": {
                    "market": "ready",
                    "quant": "cached",
                    "discipline": "missing",
                    "margin_etf": "cached",
                    "next_ticket": "ready",
                    "strategy_execution": "ready",
                },
                "must_not_do": ["不追高", "不加融资"],
            },
            "strategy_execution_packet": {
                "status": "ready",
                "action": "只观察",
                "add_condition": "突破 112 后再评估。",
                "reduce_condition": "跌破 104 或纪律信号转弱时降风险。",
                "invalidation_condition": "放量跌破 MA20，本轮持仓观察失效。",
                "deepseek_called": False,
            },
            "radar_scan_results": {
                "generated_at": f"{today}T09:40:00",
                "rule_rows": [
                    {"candidate": {"ticker": "300750.SZ", "name": "宁德时代"}, "score": {"total_score": 82, "battle_state": "等验证", "one_sentence_conclusion": "放量突破再纳入。"}},
                    {"candidate": {"ticker": "512480.SH", "name": "半导体 ETF"}, "score": {"total_score": 76, "battle_state": "只观察"}},
                    {"candidate": {"ticker": "600519.SH", "name": "贵州茅台"}, "score": {"total_score": 69, "battle_state": "暂不纳入"}},
                    {"candidate": {"ticker": "000001.SZ", "name": "平安银行"}, "score": {"total_score": 50, "battle_state": "暂不纳入"}},
                ],
            },
            "legacy_margin_etf_allocation_result": {
                "current_margin_debt_ratio": 30,
                "recommended_margin_ratio": 25,
                "recommended_cash_ratio": 20,
                "today_main_direction": "科技成长ETF",
                "selected_etf_candidates": {
                    "科技成长ETF": [
                        {"etf_code": "512480.SH", "etf_name": "半导体 ETF", "total_score": 78},
                        {"etf_code": "560780.SH", "etf_name": "半导体设备ETF广发", "total_score": 74},
                    ],
                    "防守ETF": [
                        {"etf_code": "518880.SH", "etf_name": "黄金 ETF", "total_score": 66},
                    ],
                },
                "watch_not_chase": ["半导体 ETF 不追高，等待回踩验证。"],
            },
        }
        profile = {
            "ticker": "002008.SZ",
            "name": "大族激光",
            "cost_price": 108,
            "holding_units": 3000,
            "current_price": None,
            "investment_horizon": "短中期",
            "normalized_position_state": "已持仓",
            "profit_state": "行情失败，不计算实时浮盈亏。",
        }

        payload = snapshot.build_home_action_snapshot(
            state,
            target="002008.SZ",
            position_profile=profile,
            now=f"{today}T09:45:00",
        )

        self.assertFalse(payload["is_empty"])
        self.assertEqual(payload["holding_action"]["ticker"], "002008.SZ")
        self.assertEqual(payload["holding_action"]["cost"], 108)
        self.assertEqual(payload["holding_action"]["shares"], 3000)
        self.assertEqual(payload["holding_action"]["investment_horizon"], "短中期")
        self.assertIsNone(payload["holding_action"]["current_price"])
        self.assertIn("不计算实时浮盈亏", payload["holding_action"]["floating_pnl_text"])
        self.assertEqual(len(payload["next_ticket_candidates"]), 3)
        self.assertEqual(payload["margin_etf_summary"]["current_margin_ratio"], 30)
        self.assertEqual(payload["margin_etf_summary"]["recommended_margin_ratio"], 25)
        self.assertEqual(len(payload["margin_etf_summary"]["recommended_etfs"]), 3)
        self.assertIn("纪律", payload["risk_alerts"]["data_gaps"])
        self.assertEqual(payload["data_freshness"]["label"], "今日已刷新")
        self.assertFalse(payload["deepseek_called"])

    def test_data_capability_is_persisted_in_home_snapshot(self):
        today = _dt.date.today().isoformat()
        state = {
            "command_center_decision_packet": {
                "status": "ready",
                "overall_action": "只观察",
                "updated_at": f"{today}T09:30:00",
            },
            "a_share_professional_data_capability": {
                "source": "Tushare A股专业事实",
                "checked_at": f"{today}T09:35:00",
                "items": [
                    {"section": "moneyflow", "label": "个股资金流", "api": "moneyflow", "capability_state": "available", "status": "可用"},
                    {"section": "margin", "label": "融资融券", "api": "margin_detail", "capability_state": "permission_denied", "status": "权限不足"},
                    {"section": "dragon_tiger", "label": "龙虎榜", "api": "top_list", "capability_state": "empty_recent", "status": "近期无数据"},
                ],
                "deepseek_called": False,
            },
        }

        payload = snapshot.build_home_action_snapshot(state, target="002008.SZ", now=f"{today}T09:40:00")
        capability = payload["data_capability"]

        self.assertEqual(capability["source"], "Tushare A股专业事实")
        self.assertEqual(capability["available_count"], 1)
        self.assertEqual(capability["restricted_count"], 1)
        self.assertEqual(capability["pending_count"], 1)
        self.assertIn("可用：个股资金流", capability["summary"])
        self.assertIn("受限：融资融券", capability["summary"])
        self.assertFalse(capability["deepseek_called"])

    def test_loaded_home_snapshot_keeps_data_capability(self):
        today = _dt.date.today().isoformat()
        with tempfile.TemporaryDirectory() as tmp:
            payload = snapshot.build_home_action_snapshot(
                {
                    "command_center_decision_packet": {
                        "status": "ready",
                        "overall_action": "等待",
                        "updated_at": f"{today}T10:00:00",
                    },
                    "last_data_source_healthcheck": {
                        "tushare": {
                            "source": "Tushare",
                            "checked_at": f"{today}T10:01:00",
                            "items": [
                                {"api": "limit_cpt_list", "capability_state": "disabled_this_session", "status": "本会话跳过"}
                            ],
                        }
                    },
                },
                target="002008.SZ",
                now=f"{today}T10:02:00",
            )
            snapshot.save_home_action_snapshot(payload, base_dir=tmp)
            loaded = snapshot.load_home_action_snapshot(base_dir=tmp)

        self.assertIn("本会话跳过", json.dumps(loaded["data_capability"], ensure_ascii=False))
        self.assertFalse(loaded["data_capability"]["deepseek_called"])

    def test_home_snapshot_prefers_unified_data_capability_from_healthcheck(self):
        today = _dt.date.today().isoformat()
        state = {
            "command_center_decision_packet": {
                "status": "ready",
                "overall_action": "等待",
                "updated_at": f"{today}T10:00:00",
            },
            "last_data_source_healthcheck": {
                "data_capability": {
                    "source": "Unified data capability",
                    "checked_at": f"{today}T10:01:00",
                    "items": [
                        {"provider": "Tushare", "api": "moneyflow", "label": "个股资金流", "capability_state": "available", "status": "可用"},
                        {"provider": "Supabase", "api": "brain_memory", "label": "brain_memory", "capability_state": "not_configured", "status": "未配置"},
                        {"provider": "AkShare", "api": "akshare_manual_refresh", "label": "AkShare 重型刷新", "capability_state": "requires_manual_refresh", "status": "需要手动刷新"},
                    ],
                    "deepseek_called": False,
                },
                "tushare": {
                    "source": "Tushare",
                    "items": [
                        {"api": "daily", "label": "daily", "capability_state": "available", "status": "可用"},
                    ],
                },
            },
        }

        payload = snapshot.build_home_action_snapshot(state, target="002008.SZ", now=f"{today}T10:02:00")
        capability = payload["data_capability"]
        dumped = json.dumps(capability, ensure_ascii=False)

        self.assertEqual(capability["source"], "Unified data capability")
        self.assertIn("Supabase", dumped)
        self.assertIn("AkShare 重型刷新", dumped)
        self.assertIn("需要手动刷新", dumped)
        self.assertFalse(capability["deepseek_called"])

    def test_home_snapshot_persists_command_center_facts_packet(self):
        today = _dt.date.today().isoformat()
        state = {
            "command_center_decision_packet": {
                "status": "ready",
                "overall_action": "只观察",
                "updated_at": f"{today}T10:00:00",
            },
            "command_center_facts_packet": {
                "status": "partial",
                "market": "A股",
                "ticker": "002008.SZ",
                "summary": "A股事实：可用 1，受限 1，待验证 3。",
                "items": [
                    {
                        "key": "moneyflow",
                        "label": "个股资金流",
                        "status": "通过",
                        "state": "available",
                        "evidence": "20260602 主力净额 1.23。",
                        "source": "Tushare",
                    },
                    {
                        "key": "margin",
                        "label": "融资融券",
                        "status": "权限不足",
                        "state": "permission_denied",
                        "risk": "权限不足",
                        "source": "Tushare",
                    },
                ],
                "deepseek_called": False,
            },
        }

        payload = snapshot.build_home_action_snapshot(state, target="002008.SZ", now=f"{today}T10:05:00")
        dumped = json.dumps(payload["facts_packet"], ensure_ascii=False)

        self.assertIn("个股资金流", dumped)
        self.assertIn("权限不足", dumped)
        self.assertFalse(payload["facts_packet"]["deepseek_called"])

    def test_local_snapshot_wins_after_restart_when_session_is_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            saved = snapshot.build_home_action_snapshot(
                {
                    "command_center_decision_packet": {
                        "status": "ready",
                        "overall_action": "降风险",
                        "updated_at": "2026-06-01T10:00:00",
                    }
                },
                target="002008.SZ",
            )
            snapshot.save_home_action_snapshot(saved, base_dir=tmp)
            loaded = snapshot.load_home_action_snapshot(base_dir=tmp)
            session_empty = snapshot.build_home_action_snapshot({}, target="002008.SZ")
            chosen = snapshot.choose_home_action_snapshot(session_empty, loaded)

        self.assertEqual(chosen["today_action"]["overall_action"], "降风险")
        self.assertFalse(chosen["deepseek_called"])

    def test_loaded_snapshot_recomputes_freshness_from_timestamp(self):
        today = _dt.date.today()
        yesterday = (today - _dt.timedelta(days=1)).isoformat()
        with tempfile.TemporaryDirectory() as tmp:
            saved = snapshot.build_home_action_snapshot(
                {
                    "command_center_decision_packet": {
                        "status": "ready",
                        "overall_action": "只观察",
                        "updated_at": f"{yesterday}T10:00:00",
                    }
                },
                target="002008.SZ",
                now=f"{yesterday}T10:00:00",
            )
            saved["data_freshness"] = {
                "state": "today",
                "label": "今日已刷新",
                "last_updated": f"{yesterday}T10:00:00",
                "deepseek_called": False,
            }
            snapshot.save_home_action_snapshot(saved, base_dir=tmp)
            loaded = snapshot.load_home_action_snapshot(base_dir=tmp)

        self.assertEqual(loaded["data_freshness"]["state"], "stale")
        self.assertEqual(loaded["data_freshness"]["label"], "使用缓存")
        self.assertEqual(loaded["data_freshness"]["last_updated"], f"{yesterday}T10:00:00")

    def test_margin_ratio_can_be_inferred_from_local_account_state(self):
        summary = snapshot.build_margin_etf_summary(
            {
                "margin_total_asset": 1300000,
                "margin_cash_balance": 100000,
                "margin_stock_value": 900000,
                "margin_etf_value": 300000,
                "margin_debt": 300000,
            }
        )

        self.assertEqual(summary["current_margin_ratio"], 30)

    def test_data_gap_labels_are_user_facing(self):
        payload = snapshot.build_home_action_snapshot({}, target="002008.SZ")

        self.assertIn("今日总决策", payload["risk_alerts"]["data_gaps"])
        self.assertNotIn("decision", payload["risk_alerts"]["data_gaps"])


if __name__ == "__main__":
    unittest.main()
