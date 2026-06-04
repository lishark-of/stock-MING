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
        self.assertIn("decision_loop_status", payload)
        self.assertEqual(len(payload["decision_loop_status"]["items"]), 6)
        self.assertFalse(payload["decision_loop_status"]["deepseek_called"])

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
        loop_items = {item["key"]: item for item in loaded["decision_loop_status"]["items"]}
        self.assertEqual(loop_items["decision"]["status"], "ready")
        self.assertEqual(loop_items["deepseek"]["status"], "manual")

    def test_attach_decision_loop_status_keeps_recovery_navigation_action(self):
        payload = snapshot.attach_decision_loop_status(
            {
                "data_capability_console": {"blocked_count": 1, "headline": "数据能力有 1 个阻断项"},
                "data_recovery_center": {
                    "decision_priority_queue": [
                        {
                            "key": "p0:command_center_moneyflow_packet",
                            "source_type": "data_source",
                            "priority_label": "P0 阻断交易判断",
                            "label": "个股资金流",
                            "status": "permission_denied",
                            "status_label": "权限不足",
                            "action_label": "手动刷新个股资金流",
                            "toolbox_entry": "高级工具箱 / 今日关注池",
                            "workspace_target": "高级工具箱（旧版保留）",
                            "workspace_state_key": "workspace_mode_v2",
                            "legacy_tab_state_key": "legacy_workspace_selected_tab",
                            "legacy_tab": "今日关注池",
                            "writes_packet": "command_center_moneyflow_packet",
                            "refresh_policy": "button_gated",
                        }
                    ]
                },
            }
        )
        loop_status = payload["decision_loop_status"]
        action = loop_status["recovery_actions"][0]
        navigation_state = snapshot.build_tool_recovery_navigation_state(action)

        self.assertEqual(loop_status["status"], "blocked")
        self.assertEqual(action["loop_key"], "data_capability")
        self.assertEqual(navigation_state["workspace_mode_v2"], "高级工具箱（旧版保留）")
        self.assertEqual(navigation_state["legacy_workspace_selected_tab"], "今日关注池")
        self.assertEqual(navigation_state["command_center_last_tool_recovery_writes_packet"], "command_center_moneyflow_packet")
        self.assertFalse(action["deepseek_called"])

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
        self.assertEqual(items[0]["decision_brief"]["execution_label"], "可准备")
        self.assertFalse(items[0]["decision_brief"]["deepseek_called"])

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
        self.assertEqual(items[0]["decision_brief"]["execution_label"], "可准备")

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
        self.assertTrue(payload["next_ticket_candidates"][0]["evidence_items"])
        self.assertTrue(payload["next_ticket_candidates"][0]["evidence_chain"])
        self.assertEqual(payload["next_ticket_candidates"][0]["evidence_chain"][0]["writes_packet"], "command_center_moneyflow_packet")
        self.assertEqual(payload["next_ticket_candidates"][0]["decision_brief"]["execution_label"], "等验证")
        self.assertIn("资金流", payload["next_ticket_candidates"][0]["decision_brief"]["missing_evidence"])
        self.assertIn("高级工具箱", payload["next_ticket_candidates"][0]["decision_brief"]["recovery_route"])
        self.assertIn("evidence_recovery_impact", payload["next_ticket_candidates"][0])
        self.assertIn("evidence_recovery_summary", payload["next_ticket_candidates"][0])
        self.assertIn("候选不是买入指令", payload["next_ticket_candidates"][0]["action_guardrail"])
        self.assertIn("不会自动全市场扫描", payload["next_ticket_candidates"][0]["manual_required_text"])
        self.assertFalse(payload["radar_packet"]["deepseek_called"])

    def test_next_ticket_missing_evidence_enters_recovery_center(self):
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
                            "score_notes": {"data_gaps": ["资金流待验证", "龙虎榜待验证"]},
                        },
                    },
                ],
            },
        }

        payload = snapshot.build_home_action_snapshot(state, target="002008.SZ", now=f"{today}T10:02:00")
        actions = payload["next_ticket_evidence_recovery_actions"]
        center = payload["data_recovery_center"]
        writes_packets = {item["writes_packet"] for item in actions}
        center_writes_packets = {item["writes_packet"] for item in center["actions"]}
        source_groups = {item["key"]: item for item in center["groups"]}

        self.assertIn("command_center_moneyflow_packet", writes_packets)
        self.assertIn("command_center_dragon_tiger_packet", writes_packets)
        self.assertIn("command_center_moneyflow_packet", center_writes_packets)
        self.assertIn("next_ticket_evidence", source_groups)
        self.assertGreaterEqual(source_groups["next_ticket_evidence"]["count"], 2)
        first_action = next(item for item in actions if item["writes_packet"] == "command_center_moneyflow_packet")
        self.assertEqual(first_action["refresh_policy"], "button_gated")
        self.assertEqual(first_action["legacy_tab"], "今日关注池")
        self.assertIn("300750.SZ", first_action["reason"])
        self.assertFalse(first_action["deepseek_called"])
        navigation_state = snapshot.build_tool_recovery_navigation_state(first_action)
        self.assertEqual(navigation_state["workspace_mode_v2"], "高级工具箱（旧版保留）")
        self.assertEqual(navigation_state["legacy_workspace_selected_tab"], "今日关注池")
        self.assertFalse(center["deepseek_called"])
        json.dumps(payload, ensure_ascii=False)

    def test_next_ticket_evidence_recovery_results_describe_candidate_impact(self):
        payload = snapshot.attach_next_ticket_evidence_recovery_results(
            {
                "next_ticket_candidates": [
                    {
                        "ticker": "300750.SZ",
                        "name": "宁德时代",
                        "decision_brief": {"execution_label": "等验证", "deepseek_called": False},
                        "evidence_chain": [
                            {
                                "key": "moneyflow",
                                "label": "资金流",
                                "status": "missing",
                                "writes_packet": "command_center_moneyflow_packet",
                            },
                            {
                                "key": "dragon_tiger",
                                "label": "龙虎榜",
                                "status": "missing",
                                "writes_packet": "command_center_dragon_tiger_packet",
                            },
                        ],
                    }
                ],
                "command_center_moneyflow_packet": {
                    "status": "ready",
                    "updated_at": "2026-06-04T10:00:00",
                    "source": "Tushare moneyflow",
                    "items": [{"ticker": "300750.SZ"}],
                },
                "command_center_dragon_tiger_packet": {
                    "status": "failed",
                    "data_status": "permission_denied",
                    "status_label": "权限不足",
                    "source": "Tushare top_list",
                },
            }
        )
        candidate = payload["next_ticket_candidates"][0]
        by_label = {item["label"]: item for item in candidate["evidence_recovery_items"]}

        self.assertEqual(by_label["资金流"]["status_label"], "已回流")
        self.assertEqual(by_label["龙虎榜"]["status_label"], "权限不足")
        self.assertEqual(candidate["evidence_recovery_impact"]["label"], "仍不可执行")
        self.assertIn("仍阻断 1", candidate["evidence_recovery_summary"])
        self.assertIn("候选不能升级", candidate["evidence_recovery_impact"]["impact_text"])
        self.assertEqual(candidate["decision_brief"]["recovery_impact_label"], "仍不可执行")
        self.assertFalse(candidate["evidence_recovery_impact"]["deepseek_called"])
        json.dumps(payload, ensure_ascii=False)

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
        self.assertTrue(payload["etf_packet"]["recommended_etfs"][0]["evidence_items"])
        self.assertIn("不会自动全量发现", payload["etf_packet"]["recommended_etfs"][0]["manual_required_text"])
        self.assertEqual(payload["margin_etf_summary"]["recommended_margin_ratio"], 20)
        self.assertEqual(payload["margin_etf_summary"]["recommended_etfs"][0]["name"], "半导体设备ETF广发")
        self.assertTrue(payload["margin_etf_summary"]["recommended_etfs"][0]["evidence_items"])
        self.assertTrue(payload["margin_etf_summary"]["recommended_etfs"][0]["evidence_chain"])
        self.assertIn("可参考", payload["margin_etf_summary"]["recommended_etfs"][0]["evidence_chain_summary"])
        self.assertIn("evidence_recovery_impact", payload["margin_etf_summary"]["recommended_etfs"][0])
        self.assertIn("evidence_recovery_summary", payload["margin_etf_summary"]["recommended_etfs"][0])
        self.assertIn("不能放大仓位", payload["margin_etf_summary"]["recommended_etfs"][0]["action_guardrail"])
        self.assertIn("不追高 ETF", payload["margin_etf_summary"]["watch_not_chase"])
        self.assertFalse(payload["etf_packet"]["deepseek_called"])

    def test_margin_etf_evidence_recovery_results_describe_position_impact(self):
        payload = snapshot.attach_margin_etf_evidence_recovery_results(
            {
                "margin_etf_summary": {
                    "recommended_etfs": [
                        {
                            "code": "560780.SH",
                            "name": "半导体设备ETF广发",
                            "evidence_chain": [
                                {
                                    "key": "tracking_index",
                                    "label": "跟踪指数",
                                    "status": "ready",
                                    "value": "中证半导体设备",
                                },
                                {
                                    "key": "liquidity",
                                    "label": "流动性",
                                    "status": "missing",
                                    "value": "待验证",
                                },
                                {
                                    "key": "margin_cash",
                                    "label": "融资/现金",
                                    "status": "missing",
                                    "value": "待验证",
                                },
                            ],
                        }
                    ],
                },
                "etf_packet": {
                    "status": "ready",
                    "updated_at": "2026-06-04T10:00:00",
                    "source": "融资 ETF 本地配置快照",
                    "recommended_etfs": [{"code": "560780.SH"}],
                },
                "command_center_margin_packet": {
                    "status": "failed",
                    "data_status": "permission_denied",
                    "status_label": "权限不足",
                    "source": "Tushare margin_detail",
                },
            }
        )
        etf = payload["margin_etf_summary"]["recommended_etfs"][0]
        by_label = {item["label"]: item for item in etf["evidence_recovery_items"]}

        self.assertEqual(by_label["跟踪指数"]["status_label"], "已验证")
        self.assertEqual(by_label["流动性"]["status_label"], "待验证")
        self.assertEqual(by_label["融资/现金"]["status_label"], "权限不足")
        self.assertEqual(etf["evidence_recovery_impact"]["label"], "仍不可放大")
        self.assertIn("已验证 1", etf["evidence_recovery_summary"])
        self.assertIn("仍阻断 1", etf["evidence_recovery_summary"])
        self.assertIn("不能加融资", etf["evidence_recovery_impact"]["impact_text"])
        self.assertFalse(etf["evidence_recovery_impact"]["deepseek_called"])
        json.dumps(payload, ensure_ascii=False)

    def test_home_snapshot_persists_market_profile_evidence(self):
        today = _dt.date.today().isoformat()
        state = {
            "command_center_decision_packet": {
                "status": "ready",
                "overall_action": "只观察",
                "updated_at": f"{today}T10:00:00",
            },
        }

        payload = snapshot.build_home_action_snapshot(state, target="002008.SZ", now=f"{today}T10:03:00")
        market_profile = payload["market_profile_evidence"]
        dumped = json.dumps(market_profile, ensure_ascii=False)

        self.assertEqual(market_profile["market_type"], "A股")
        self.assertEqual(market_profile["market_label"], "A股个股")
        self.assertIn("Tushare", dumped)
        self.assertIn("资金流", dumped)
        self.assertFalse(market_profile["deepseek_called"])

    def test_loaded_home_snapshot_keeps_market_profile_evidence(self):
        today = _dt.date.today().isoformat()
        with tempfile.TemporaryDirectory() as tmp:
            payload = snapshot.build_home_action_snapshot(
                {
                    "command_center_decision_packet": {
                        "status": "ready",
                        "overall_action": "等待",
                        "updated_at": f"{today}T10:00:00",
                    },
                },
                target="AAPL",
                now=f"{today}T10:02:00",
            )
            snapshot.save_home_action_snapshot(payload, base_dir=tmp)
            loaded = snapshot.load_home_action_snapshot(base_dir=tmp)

        self.assertEqual(loaded["market_profile_evidence"]["market_type"], "美股")
        self.assertIn("财报", json.dumps(loaded["market_profile_evidence"], ensure_ascii=False))
        self.assertFalse(loaded["market_profile_evidence"]["deepseek_called"])

    def test_empty_snapshot_market_profile_does_not_create_action_data(self):
        payload = snapshot.build_home_action_snapshot(target="AAPL")

        self.assertTrue(payload["is_empty"])
        self.assertEqual(payload["market_profile_evidence"]["market_type"], "美股")
        self.assertFalse(snapshot.has_action_snapshot_data(payload))

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
        self.assertEqual(payload["discipline_packet"]["backtest_status"], "已读取回测缓存")
        self.assertTrue(payload["discipline_packet"]["metric_items"])
        self.assertTrue(payload["discipline_packet"]["evidence_items"])
        self.assertEqual(payload["discipline_packet"]["decision_brief"]["action_mode"], "usable_evidence")
        self.assertIn("不直接决定买卖", payload["discipline_packet"]["decision_brief"]["guardrail_text"])
        self.assertIn("不会自动跑回测", payload["discipline_packet"]["backtest_required_text"])
        self.assertFalse(payload["discipline_packet"]["deepseek_called"])

    def test_deepseek_defaults_to_not_called(self):
        payload = snapshot.build_home_action_snapshot({
            "command_center_decision_packet": {"overall_action": "等待"}
        })

        self.assertFalse(payload["deepseek_called"])
        self.assertFalse(payload["data_freshness"]["deepseek_called"])

    def test_hard_risk_packet_feeds_home_risk_alerts(self):
        today = _dt.date.today().isoformat()
        payload = snapshot.build_home_action_snapshot(
            {
                "command_center_decision_packet": {
                    "status": "ready",
                    "overall_action": "只观察",
                    "updated_at": f"{today}T10:00:00",
                    "must_not_do": ["不追高"],
                },
                "command_center_hard_risk_packet": {
                    "status": "ready",
                    "data_status": "ready",
                    "ticker": "002008.SZ",
                    "risk_state": "风险线索存在",
                    "updated_at": f"{today}T10:08:00",
                    "risk_items": [
                        {
                            "type": "股东减持",
                            "message": "控股股东减持计划待复核",
                            "date": today.replace("-", ""),
                            "source": "Tushare stk_holdertrade",
                        }
                    ],
                    "deepseek_called": False,
                },
            },
            target="002008.SZ",
            now=f"{today}T10:10:00",
        )
        alerts = payload["risk_alerts"]
        dumped = json.dumps(alerts, ensure_ascii=False)

        self.assertIn("公告/硬风险线索未复核前不加仓", dumped)
        self.assertIn("控股股东减持计划待复核", dumped)
        self.assertIn("公告/硬风险存在待复核线索", alerts["data_gaps"])
        self.assertEqual(alerts["hard_risk_status"], "风险线索存在")
        self.assertFalse(payload["hard_risk_packet"]["deepseek_called"])
        self.assertFalse(payload["deepseek_called"])

    def test_loaded_snapshot_keeps_hard_risk_alerts(self):
        today = _dt.date.today().isoformat()
        with tempfile.TemporaryDirectory() as tmp:
            payload = snapshot.build_home_action_snapshot(
                {
                    "command_center_decision_packet": {
                        "status": "ready",
                        "overall_action": "等待",
                        "updated_at": f"{today}T10:00:00",
                    },
                    "command_center_hard_risk_packet": {
                        "status": "ready",
                        "data_status": "ready",
                        "ticker": "002008.SZ",
                        "risk_state": "风险线索存在",
                        "updated_at": f"{today}T10:08:00",
                        "risk_items": [{"type": "股权质押", "message": "质押比例较高", "source": "Tushare pledge_stat"}],
                        "deepseek_called": False,
                    },
                },
                target="002008.SZ",
                now=f"{today}T10:12:00",
            )
            snapshot.save_home_action_snapshot(payload, base_dir=tmp)
            loaded = snapshot.load_home_action_snapshot(base_dir=tmp)

        dumped = json.dumps(loaded["risk_alerts"], ensure_ascii=False)
        self.assertIn("质押比例较高", dumped)
        self.assertEqual(loaded["risk_alerts"]["hard_risk_status"], "风险线索存在")
        self.assertFalse(loaded["hard_risk_packet"]["deepseek_called"])

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
        matrix = payload["a_share_capability_matrix"]
        matrix_by_key = {item["key"]: item for item in matrix["items"]}

        self.assertEqual(capability["source"], "Unified data capability")
        self.assertEqual(capability["available_count"], 1)
        self.assertEqual(capability["restricted_count"], 1)
        self.assertGreaterEqual(capability["pending_count"], 1)
        self.assertIn("可用：个股资金流", capability["summary"])
        self.assertIn("受限：融资融券", capability["summary"])
        self.assertIn("待验证：龙虎榜", capability["summary"])
        self.assertEqual(matrix_by_key["moneyflow"]["state"], "available")
        self.assertEqual(matrix_by_key["margin"]["state"], "permission_denied")
        self.assertEqual(matrix_by_key["dragon_tiger"]["state"], "empty_recent")
        self.assertIn("拉满基础数据", matrix["tushare_gap_explainer"]["headline"])
        self.assertIn("融资融券", json.dumps(matrix["tushare_gap_explainer"], ensure_ascii=False))
        self.assertFalse(matrix["deepseek_called"])
        self.assertFalse(capability["deepseek_called"])

    def test_empty_data_capability_summary_names_all_external_providers(self):
        capability = snapshot.build_data_capability_snapshot({})

        self.assertIn("Tushare", capability["summary"])
        self.assertIn("AkShare", capability["summary"])
        self.assertIn("yfinance", capability["summary"])
        self.assertIn("Supabase", capability["summary"])
        self.assertFalse(capability["deepseek_called"])

    def test_home_snapshot_prefers_current_a_share_capability_over_stale_command_packet(self):
        today = _dt.date.today().isoformat()
        state = {
            "command_center_decision_packet": {
                "status": "ready",
                "overall_action": "只观察",
                "updated_at": f"{today}T09:30:00",
            },
            "command_center_data_capability_packet": {
                "source": "Unified data capability",
                "checked_at": f"{today}T09:00:00",
                "items": [
                    {
                        "provider": "Tushare",
                        "section": "margin",
                        "label": "融资融券",
                        "api": "margin_detail",
                        "capability_state": "available",
                        "status": "可用",
                    }
                ],
                "deepseek_called": False,
            },
            "a_share_professional_data_capability": {
                "source": "Tushare A股专业事实",
                "checked_at": f"{today}T09:35:00",
                "items": [
                    {
                        "provider": "Tushare",
                        "section": "margin",
                        "label": "融资融券",
                        "api": "margin_detail",
                        "capability_state": "permission_denied",
                        "status": "权限不足",
                        "error": "当前权限不足",
                    }
                ],
                "deepseek_called": False,
            },
        }

        payload = snapshot.build_home_action_snapshot(state, target="002008.SZ", now=f"{today}T09:40:00")
        capability = payload["data_capability"]
        matrix_by_key = {item["key"]: item for item in payload["a_share_capability_matrix"]["items"]}
        dumped = json.dumps(payload["data_issue_explainer"], ensure_ascii=False)

        self.assertEqual(capability["source"], "Unified data capability")
        self.assertEqual(capability["restricted_count"], 1)
        self.assertEqual(matrix_by_key["margin"]["state"], "permission_denied")
        self.assertIn("权限不足", dumped)
        self.assertFalse(capability["deepseek_called"])

    def test_home_snapshot_builds_capability_from_legacy_a_share_facts(self):
        today = _dt.date.today().isoformat()
        state = {
            "command_center_decision_packet": {
                "status": "ready",
                "overall_action": "只观察",
                "updated_at": f"{today}T09:30:00",
            },
            "a_share_professional_facts": {
                "stock_code": "002008",
                "updated_at": f"{today}T09:35:00",
                "moneyflow": {
                    "available": True,
                    "api": "moneyflow",
                    "date": "20260603",
                    "updated_at": f"{today}T09:35:00",
                },
                "dragon_tiger": {
                    "available": False,
                    "api": "top_list/top_inst",
                    "message": "近30日未见龙虎榜上榜记录",
                    "updated_at": f"{today}T09:35:00",
                },
                "margin": {
                    "available": False,
                    "api": "margin_detail",
                    "error": "抱歉，您没有访问该接口的权限",
                    "updated_at": f"{today}T09:35:00",
                },
            },
        }

        payload = snapshot.build_home_action_snapshot(state, target="002008.SZ", now=f"{today}T09:40:00")
        capability = payload["data_capability"]
        console = payload["data_capability_console"]
        dumped = json.dumps(payload, ensure_ascii=False)

        self.assertEqual(capability["source"], "Tushare A股专业事实")
        self.assertEqual(capability["available_count"], 1)
        self.assertGreaterEqual(capability["restricted_count"], 1)
        self.assertGreaterEqual(capability["pending_count"], 1)
        self.assertIn("个股资金流", dumped)
        self.assertIn("龙虎榜", dumped)
        self.assertIn("融资融券", dumped)
        self.assertEqual(console["status"], "blocked")
        self.assertFalse(capability["deepseek_called"])
        self.assertFalse(console["deepseek_called"])

    def test_home_snapshot_builds_user_visible_a_share_diagnostic(self):
        today = _dt.date.today().isoformat()
        state = {
            "command_center_decision_packet": {
                "status": "ready",
                "overall_action": "只观察",
                "updated_at": f"{today}T09:30:00",
            },
            "a_share_professional_facts": {
                "verified_technical_facts": {"available": False, "missing": ["verified_technical_facts"]},
                "moneyflow": {
                    "available": False,
                    "api": "moneyflow",
                    "error": "无接口访问权限",
                    "updated_at": f"{today}T09:35:00",
                },
                "dragon_tiger": {
                    "available": False,
                    "api": "top_list/top_inst",
                    "warning": "近30日暂未取得可验证数据",
                    "updated_at": f"{today}T09:35:00",
                },
                "margin": {"available": True, "api": "margin_detail", "date": "20260603"},
                "limit_emotion": {"available": True, "api": "stk_limit"},
            },
        }

        payload = snapshot.build_home_action_snapshot(state, target="002008.SZ", now=f"{today}T09:40:00")
        diagnostic = payload["a_share_user_data_diagnostic"]
        dumped = json.dumps(diagnostic, ensure_ascii=False)

        self.assertEqual(diagnostic["tone"], "warning")
        self.assertIn("权限不足", diagnostic["headline"])
        self.assertIn("个股资金流", dumped)
        self.assertIn("龙虎榜", dumped)
        self.assertIn("暂未取得", dumped)
        self.assertIn("手动按钮", dumped)
        self.assertIn("command_center_moneyflow_packet", dumped)
        self.assertIn("command_center_dragon_tiger_packet", dumped)
        self.assertIn("筹码 / 胜率", dumped)
        self.assertIn("公告 / 硬风险", dumped)
        self.assertIn("command_center_chip_packet", dumped)
        self.assertIn("command_center_hard_risk_packet", dumped)
        self.assertIn("页面打开不会自动请求", diagnostic["safe_mode_text"])
        self.assertEqual(diagnostic["recovery_actions"][0]["label"], "个股资金流")
        self.assertEqual(diagnostic["recovery_actions"][0]["refresh_policy"], "button_gated")
        self.assertEqual(diagnostic["recovery_actions"][0]["legacy_tab"], "今日关注池")
        self.assertIn("高级工具箱", diagnostic["recovery_actions"][0]["navigation_label"])
        self.assertEqual(diagnostic["status_console"]["title"], "A股数据能力控制台")
        self.assertIn("受限 1", diagnostic["status_console"]["summary"])
        self.assertIn("暂无数据 2", diagnostic["status_console"]["summary"])
        self.assertIn("待手动 1", diagnostic["status_console"]["summary"])
        self.assertEqual(diagnostic["status_console"]["decision_readiness_label"], "阻断加仓")
        self.assertFalse(payload["deepseek_called"])

    def test_home_snapshot_user_diagnostic_adds_chip_and_hard_risk_recovery_when_missing(self):
        today = _dt.date.today().isoformat()
        state = {
            "command_center_decision_packet": {
                "status": "ready",
                "overall_action": "只观察",
                "updated_at": f"{today}T09:30:00",
            },
            "a_share_professional_facts": {
                "verified_technical_facts": {"available": True},
                "moneyflow": {"available": True, "api": "moneyflow"},
                "dragon_tiger": {"available": True, "api": "top_list"},
                "margin": {"available": True, "api": "margin_detail"},
                "limit_emotion": {"available": True, "api": "stk_limit"},
            },
        }

        payload = snapshot.build_home_action_snapshot(state, target="002008.SZ", now=f"{today}T09:40:00")
        diagnostic = payload["a_share_user_data_diagnostic"]
        dumped = json.dumps(diagnostic, ensure_ascii=False)

        self.assertIn("筹码 / 胜率", dumped)
        self.assertIn("公告 / 硬风险", dumped)
        chip_action = next(action for action in diagnostic["recovery_actions"] if action["key"] == "chip_radar")
        hard_action = next(action for action in diagnostic["recovery_actions"] if action["key"] == "hard_risk")
        self.assertEqual(chip_action["writes_packet"], "command_center_chip_packet")
        self.assertEqual(chip_action["refresh_policy"], "button_gated")
        self.assertEqual(hard_action["legacy_tab"], "天眼风控")
        self.assertEqual(hard_action["writes_packet"], "command_center_hard_risk_packet")
        self.assertIn("暂无数据 1", diagnostic["status_console"]["summary"])
        self.assertIn("待手动 1", diagnostic["status_console"]["summary"])
        self.assertFalse(chip_action["deepseek_called"])
        self.assertFalse(hard_action["deepseek_called"])
        self.assertFalse(payload["deepseek_called"])

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
        absence = loaded["old_workspace_data_absence_ledger"]
        self.assertEqual(absence["title"], "旧工作台数据缺失原因总账")
        self.assertIn("本会话跳过", json.dumps(absence, ensure_ascii=False))
        self.assertFalse(absence["deepseek_called"])

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
        self.assertIn("provider_gap_explainer", json.dumps(payload["data_capability_console"], ensure_ascii=False))
        self.assertFalse(capability["deepseek_called"])

    def test_home_snapshot_builds_data_gap_report(self):
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
                        {"provider": "Tushare", "api": "margin_detail", "label": "融资融券", "capability_state": "permission_denied", "status": "权限不足"},
                    ],
                    "deepseek_called": False,
                }
            },
        }

        payload = snapshot.build_home_action_snapshot(state, target="002008.SZ", now=f"{today}T10:02:00")
        report = payload["data_gap_report"]

        self.assertEqual(report["available_count"], 1)
        self.assertGreaterEqual(report["restricted_count"], 1)
        self.assertIn("可信度", report["summary"])
        self.assertTrue(any("权限不足" in item for item in report["next_manual_checks"]))
        self.assertFalse(report["deepseek_called"])

    def test_home_snapshot_builds_data_issue_explainer(self):
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
                        {"provider": "Tushare", "api": "top_list", "label": "龙虎榜", "capability_state": "empty_recent", "status": "近期无数据"},
                        {"provider": "Tushare", "api": "limit_cpt_list", "label": "涨跌停/情绪", "capability_state": "disabled_this_session", "status": "本会话跳过"},
                    ],
                    "deepseek_called": False,
                }
            },
        }

        payload = snapshot.build_home_action_snapshot(state, target="002008.SZ", now=f"{today}T10:02:00")
        explainer = payload["data_issue_explainer"]
        dumped = json.dumps(explainer, ensure_ascii=False)

        self.assertEqual(explainer["status"], "ready")
        self.assertIn("Tushare 配置成功只代表 token 可用", explainer["short_answer"])
        self.assertIn("近期无记录", dumped)
        self.assertIn("本会话跳过重复请求", dumped)
        self.assertFalse(explainer["deepseek_called"])

    def test_old_workspace_data_absence_ledger_groups_root_causes(self):
        ledger = snapshot.build_old_workspace_data_absence_ledger(
            {
                "data_issue_explainer": {
                    "interface_diagnostic_items": [
                        {
                            "provider": "Tushare",
                            "api": "margin_detail",
                            "label": "融资融券",
                            "state": "permission_denied",
                            "cause_key": "permission_or_points",
                            "cause_label": "权限/积分不足",
                            "diagnostic_answer": "融资融券不是没搜到，而是权限不足。",
                        },
                        {
                            "provider": "Tushare",
                            "api": "limit_cpt_list",
                            "label": "涨跌停/情绪",
                            "state": "disabled_this_session",
                            "cause_key": "session_skip",
                            "cause_label": "本会话已跳过",
                        },
                        {
                            "provider": "Tushare",
                            "api": "top_list",
                            "label": "龙虎榜",
                            "state": "empty_recent",
                            "cause_key": "no_recent_record",
                            "cause_label": "近期无记录",
                        },
                        {
                            "provider": "AkShare",
                            "api": "akshare_manual_refresh",
                            "label": "AkShare 重型刷新",
                            "state": "requires_manual_refresh",
                            "cause_key": "manual_gate",
                            "cause_label": "需要手动触发",
                        },
                    ]
                },
                "legacy_a_share_gap_summary": {
                    "items": [
                        {
                            "key": "chip_radar",
                            "label": "筹码/胜率",
                            "status_label": "使用缓存",
                            "source": "Tushare cyq_perf/cyq_chips",
                            "writes_packet": "command_center_chip_packet",
                        }
                    ]
                },
            }
        )
        dumped = json.dumps(ledger, ensure_ascii=False)

        self.assertEqual(ledger["title"], "旧工作台数据缺失原因总账")
        self.assertEqual(ledger["status"], "blocked")
        self.assertEqual(ledger["permission_count"], 1)
        self.assertEqual(ledger["session_skip_count"], 1)
        self.assertEqual(ledger["no_recent_record_count"], 1)
        self.assertEqual(ledger["cache_or_fallback_count"], 1)
        self.assertEqual(ledger["manual_gate_count"], 1)
        self.assertIn("Tushare 拉满基础连接", ledger["short_answer"])
        self.assertIn("融资融券", dumped)
        self.assertIn("涨跌停/情绪", dumped)
        self.assertIn("龙虎榜", dumped)
        self.assertIn("筹码/胜率", dumped)
        self.assertIn("AkShare 重型刷新", dumped)
        self.assertIn("不能把权限缺口当成行情不存在", dumped)
        self.assertFalse(ledger["deepseek_called"])
        self.assertEqual(ledger["external_call_policy"], "not_triggered")
        self.assertIn("不会自动调用 Tushare", ledger["safe_mode_text"])
        by_label = {item["label"]: item for item in ledger["items"]}
        self.assertEqual(by_label["融资融券"]["writes_packet"], "command_center_margin_packet")
        self.assertEqual(by_label["融资融券"]["legacy_tab"], "融资 ETF")
        self.assertIn("手动执行后回流 command_center_margin_packet", by_label["融资融券"]["navigation_label"])
        self.assertIn("不会自动调用 DeepSeek", by_label["融资融券"]["recovery_button_context"])
        margin_navigation = snapshot.build_tool_recovery_navigation_state(by_label["融资融券"])
        self.assertEqual(margin_navigation["workspace_mode_v2"], "高级工具箱（旧版保留）")
        self.assertEqual(margin_navigation["legacy_workspace_selected_tab"], "融资 ETF")
        self.assertEqual(margin_navigation["command_center_last_tool_recovery_policy"], "navigation_only")
        self.assertEqual(by_label["涨跌停/情绪"]["writes_packet"], "command_center_limit_emotion_packet")
        self.assertEqual(by_label["涨跌停/情绪"]["legacy_tab"], "数据源体检")
        self.assertEqual(by_label["AkShare 重型刷新"]["legacy_tab"], "数据源体检")
        json.dumps(ledger, ensure_ascii=False)

    def test_home_snapshot_builds_data_capability_console(self):
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
                        {"provider": "Tushare", "api": "margin_detail", "label": "融资融券", "capability_state": "permission_denied", "status": "权限不足"},
                        {"provider": "AkShare", "api": "akshare_manual_refresh", "label": "AkShare 重型刷新", "capability_state": "requires_manual_refresh", "status": "需要手动刷新"},
                    ],
                    "deepseek_called": False,
                }
            },
        }

        payload = snapshot.build_home_action_snapshot(state, target="002008.SZ", now=f"{today}T10:02:00")
        console = payload["data_capability_console"]
        health_ledger = payload["data_health_ledger"]
        visibility = payload["command_center_data_health_visibility_summary"]
        health_timeline = payload["command_center_data_health_timeline"]
        dumped = json.dumps(console, ensure_ascii=False)

        self.assertEqual(console["status"], "blocked")
        self.assertEqual(console["available_count"], 1)
        self.assertEqual(console["blocked_count"], 1)
        self.assertEqual(console["manual_count"], 1)
        self.assertEqual(console["decision_readiness_label"], "阻断加仓")
        self.assertEqual(console["recovery_actions"][0]["label"], "融资融券")
        self.assertEqual(console["recovery_actions"][0]["writes_packet"], "command_center_margin_packet")
        self.assertIn("融资融券", console["recovery_summary"])
        self.assertEqual(health_ledger["status"], "blocked")
        self.assertTrue(any(row["label"] == "融资融券" for row in health_ledger["rows"]))
        self.assertTrue(any(row["writes_packet"] == "command_center_margin_packet" for row in health_ledger["rows"]))
        self.assertEqual(visibility, payload["data_health_visibility_summary"])
        self.assertEqual(visibility["title"], "为什么搜不到")
        self.assertEqual(visibility["status"], "blocked")
        self.assertIn("Tushare 拉满", visibility["headline"])
        self.assertIn("融资融券", visibility["permission_labels"])
        self.assertEqual(visibility["recovery_actions"][0]["manual_check_key"], "margin")
        self.assertEqual(visibility["recovery_actions"][0]["manual_check_button_label"], "手动检测融资融券")
        self.assertIn("只检测 margin_detail", visibility["recovery_actions"][0]["manual_check_instruction"])
        self.assertEqual(visibility["recovery_actions"][0]["legacy_workspace_route"]["legacy_tab"], "融资 ETF")
        self.assertEqual(visibility["items"][0]["manual_check_key"], "margin")
        self.assertFalse(visibility["deepseek_called"])
        self.assertEqual(health_timeline, payload["data_health_timeline"])
        self.assertEqual(health_timeline["title"], "接口健康时间线")
        self.assertEqual(health_timeline["status"], "blocked")
        self.assertIn("最近失败", health_timeline["summary"])
        self.assertEqual(health_timeline["items"][0]["event_type"], "last_failure")
        self.assertEqual(health_timeline["items"][0]["writes_packet"], "command_center_margin_packet")
        self.assertEqual(health_timeline["items"][0]["external_call_policy"], "not_triggered")
        self.assertFalse(health_timeline["deepseek_called"])
        timeline_actions = payload["command_center_data_health_timeline_recovery_actions"]
        self.assertEqual(timeline_actions, payload["data_health_timeline_recovery_actions"])
        self.assertEqual(timeline_actions[0]["label"], "融资融券")
        self.assertEqual(timeline_actions[0]["event_type"], "last_failure")
        self.assertEqual(timeline_actions[0]["writes_packet"], "command_center_margin_packet")
        self.assertEqual(timeline_actions[0]["legacy_tab"], "融资 ETF")
        self.assertEqual(timeline_actions[0]["external_call_policy"], "not_triggered")
        self.assertFalse(timeline_actions[0]["deepseek_called"])
        timeline_navigation = snapshot.build_tool_recovery_navigation_state(timeline_actions[0])
        self.assertEqual(timeline_navigation["workspace_mode_v2"], "高级工具箱（旧版保留）")
        self.assertEqual(timeline_navigation["legacy_workspace_selected_tab"], "融资 ETF")
        self.assertEqual(timeline_navigation["command_center_last_tool_recovery_policy"], "navigation_only")
        self.assertEqual(payload["data_recovery_actions"][0]["label"], "融资融券")
        self.assertEqual(payload["data_recovery_actions"][0]["writes_packet"], "command_center_margin_packet")
        self.assertEqual(payload["data_recovery_actions"][0]["refresh_policy"], "button_gated")
        self.assertEqual(payload["data_recovery_actions"][0]["interface_cause_key"], "permission_or_points")
        self.assertEqual(payload["data_recovery_actions"][0]["interface_cause_label"], "权限/积分不足")
        self.assertIn("专业接口已开通", payload["data_recovery_actions"][0]["interface_diagnostic_answer"])
        self.assertIn("只检测 margin_detail", payload["data_recovery_actions"][0]["recovery_button_context"])
        self.assertEqual(payload["data_recovery_actions"][0]["legacy_tab"], "融资 ETF")
        self.assertIn("手动执行后回流 command_center_margin_packet", payload["data_recovery_actions"][0]["navigation_label"])
        self.assertIn("不是“没搜到”", payload["data_recovery_actions"][0]["diagnostic_answer"])
        self.assertIn("权限/积分不足", payload["data_recovery_actions"][0]["diagnostic_answer"])
        self.assertIn("只允许观察、降风险", payload["risk_alerts"]["reduce_conditions"][0])
        self.assertTrue(any("融资融券" in item for item in payload["risk_alerts"]["data_gaps"]))
        self.assertTrue(any("AkShare 重型刷新" in item for item in payload["risk_alerts"]["data_gaps"]))
        self.assertIn("个股资金流", dumped)
        self.assertIn("融资融券", dumped)
        self.assertIn("AkShare 重型刷新", dumped)
        self.assertFalse(console["deepseek_called"])
        self.assertFalse(payload["data_recovery_actions"][0]["deepseek_called"])

    def test_data_health_timeline_recovery_actions_are_navigation_only(self):
        timeline = {
            "items": [
                {
                    "event_type": "last_success",
                    "label": "个股资金流",
                    "api": "moneyflow",
                    "writes_packet": "command_center_moneyflow_packet",
                    "status_label": "最近成功",
                },
                {
                    "event_type": "cache_used",
                    "label": "筹码/胜率",
                    "api": "cyq_perf",
                    "writes_packet": "command_center_chip_packet",
                    "status_label": "使用缓存",
                    "message": "筹码/胜率当前依赖缓存。",
                },
                {
                    "event_type": "last_failure",
                    "label": "融资融券",
                    "api": "margin_detail",
                    "writes_packet": "command_center_margin_packet",
                    "status_label": "最近失败",
                    "message": "融资融券权限不足。",
                },
                {
                    "event_type": "manual_required",
                    "label": "AkShare 重型刷新",
                    "api": "akshare_manual_refresh",
                    "writes_packet": "command_center_data_capability_packet",
                    "status_label": "需要手动刷新",
                },
            ],
            "deepseek_called": False,
        }
        before = json.dumps(timeline, ensure_ascii=False, sort_keys=True)

        actions = snapshot.build_data_health_timeline_recovery_actions(timeline)
        after = json.dumps(timeline, ensure_ascii=False, sort_keys=True)
        by_label = {item["label"]: item for item in actions}

        self.assertEqual(before, after)
        self.assertEqual(actions[0]["label"], "融资融券")
        self.assertNotIn("个股资金流", by_label)
        self.assertEqual(by_label["筹码/胜率"]["legacy_tab"], "量化推演")
        self.assertEqual(by_label["AkShare 重型刷新"]["refresh_policy"], "button_gated")
        self.assertTrue(all(item["external_call_policy"] == "not_triggered" for item in actions))
        self.assertTrue(all(item["deepseek_called"] is False for item in actions))
        navigation_state = snapshot.build_tool_recovery_navigation_state(by_label["筹码/胜率"])
        self.assertEqual(navigation_state["legacy_workspace_selected_tab"], "量化推演")
        json.dumps(actions, ensure_ascii=False)

    def test_home_recovery_action_promotes_session_skip_interface_diagnostic(self):
        today = _dt.date.today().isoformat()
        state = {
            "last_data_source_healthcheck": {
                "data_capability": {
                    "source": "Unified data capability",
                    "checked_at": f"{today}T10:01:00",
                    "items": [
                        {
                            "provider": "Tushare",
                            "api": "limit_cpt_list",
                            "label": "涨跌停/情绪",
                            "capability_state": "disabled_this_session",
                            "status": "本会话跳过",
                        }
                    ],
                    "deepseek_called": False,
                }
            },
        }

        payload = snapshot.build_home_action_snapshot(state, target="002008.SZ", now=f"{today}T10:02:00")
        action = payload["data_recovery_actions"][0]

        self.assertEqual(action["label"], "涨跌停/情绪")
        self.assertEqual(action["writes_packet"], "command_center_limit_emotion_packet")
        self.assertEqual(action["interface_cause_key"], "session_skip")
        self.assertIn("本会话跳过重复请求", action["interface_diagnostic_answer"])
        self.assertIn("只检测 limit_cpt_list", action["recovery_button_context"])
        self.assertEqual(action["legacy_tab"], "数据源体检")
        self.assertFalse(action["deepseek_called"])

    def test_loaded_home_snapshot_keeps_data_recovery_actions(self):
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
                        "data_capability": {
                            "source": "Unified data capability",
                            "checked_at": f"{today}T10:01:00",
                            "items": [
                                {"provider": "Tushare", "api": "margin_detail", "label": "融资融券", "capability_state": "permission_denied", "status": "权限不足"},
                                {"provider": "AkShare", "api": "akshare_manual_refresh", "label": "AkShare 重型刷新", "capability_state": "requires_manual_refresh", "status": "需要手动刷新"},
                            ],
                            "deepseek_called": False,
                        }
                    },
                },
                target="002008.SZ",
                now=f"{today}T10:02:00",
            )
            snapshot.save_home_action_snapshot(payload, base_dir=tmp)
            loaded = snapshot.load_home_action_snapshot(base_dir=tmp)

        dumped = json.dumps(loaded["data_recovery_actions"], ensure_ascii=False)
        self.assertIn("融资融券", dumped)
        self.assertIn("AkShare 重型刷新", dumped)
        self.assertEqual(loaded["data_recovery_actions"][0]["writes_packet"], "command_center_margin_packet")
        self.assertFalse(loaded["data_recovery_actions"][0]["deepseek_called"])
        self.assertEqual(loaded["data_recovery_center"]["title"], "数据恢复中心")
        self.assertTrue(loaded["data_recovery_center"]["actions"])
        self.assertTrue(all(item["refresh_policy"] == "button_gated" for item in loaded["data_recovery_center"]["actions"]))
        self.assertFalse(loaded["data_recovery_center"]["deepseek_called"])
        self.assertEqual(loaded["legacy_migration_map"]["title"], "旧版能力迁移地图")
        self.assertFalse(loaded["legacy_migration_map"]["deepseek_called"])

    def test_home_data_recovery_center_merges_recovery_sources(self):
        center = snapshot.build_home_data_recovery_center(
            {
                "data_recovery_actions": [
                    {
                        "label": "融资融券",
                        "status_label": "权限不足",
                        "priority": 1,
                        "diagnostic_answer": "Tushare margin_detail 权限不足。",
                        "decision_guardrail": "融资融券未恢复前不能支持加融资。",
                        "recovery_button_context": "只检测 margin_detail 并回流 command_center_margin_packet。",
                        "action_label": "手动刷新融资融券",
                        "writes_packet": "command_center_margin_packet",
                        "refresh_policy": "button_gated",
                    }
                ],
                "a_share_user_data_diagnostic": {
                    "recovery_actions": [
                        {
                            "key": "margin",
                            "label": "融资融券",
                            "status_label": "权限不足",
                            "action_label": "检测融资融券",
                            "writes_packet": "command_center_margin_packet",
                            "refresh_policy": "button_gated",
                        },
                        {
                            "key": "chip_radar",
                            "label": "筹码 / 胜率",
                            "status_label": "暂无当日数据",
                            "action_label": "检测筹码/胜率",
                            "writes_packet": "command_center_chip_packet",
                            "refresh_policy": "button_gated",
                        },
                    ]
                },
                "tool_recovery_actions": [
                    {
                        "key": "next_ticket_radar",
                        "label": "下一票雷达",
                        "status": "waiting",
                        "data_status": "missing",
                        "action_label": "手动运行下一票雷达",
                        "writes_packet": "command_center_radar_packet",
                        "refresh_policy": "button_gated",
                    }
                ],
                "data_health_timeline_recovery_actions": [
                    {
                        "key": "data_health_timeline:limit_cpt_list:empty_recent",
                        "label": "涨跌停/情绪",
                        "status": "empty_recent",
                        "status_label": "近期无数据",
                        "source_type": "data_health_timeline",
                        "source_label": "接口健康时间线",
                        "diagnostic_answer": "limit_cpt_list 近期无数据。",
                        "action_label": "手动检测涨跌停/情绪",
                        "workspace_target": "高级工具箱（旧版保留）",
                        "workspace_state_key": "workspace_mode_v2",
                        "legacy_tab_state_key": "legacy_workspace_selected_tab",
                        "legacy_tab": "数据源体检",
                        "writes_packet": "command_center_limit_emotion_packet",
                        "refresh_policy": "button_gated",
                        "deepseek_called": False,
                    }
                ],
            }
        )

        writes_packets = [item["writes_packet"] for item in center["actions"]]
        group_counts = {item["key"]: item["count"] for item in center["groups"]}
        lane_counts = {item["key"]: item["count"] for item in center["priority_lanes"]}
        lane_summaries = {item["key"]: item["summary"] for item in center["priority_lanes"]}
        decision_queue = center["decision_priority_queue"]

        self.assertEqual(center["title"], "数据恢复中心")
        self.assertEqual(center["action_count"], 4)
        self.assertEqual(writes_packets.count("command_center_margin_packet"), 1)
        self.assertIn("command_center_chip_packet", writes_packets)
        self.assertIn("command_center_radar_packet", writes_packets)
        self.assertIn("command_center_limit_emotion_packet", writes_packets)
        self.assertEqual(group_counts["data_source"], 1)
        self.assertEqual(group_counts["data_health_timeline"], 1)
        self.assertEqual(group_counts["a_share"], 1)
        self.assertEqual(group_counts["legacy_tool"], 1)
        self.assertEqual(lane_counts["p0"], 1)
        self.assertEqual(lane_counts["p1"], 2)
        self.assertEqual(lane_counts["p2"], 1)
        self.assertIn("融资融券", lane_summaries["p0"])
        self.assertIn("筹码", lane_summaries["p1"])
        self.assertIn("下一票雷达", lane_summaries["p2"])
        self.assertEqual([item["lane_key"] for item in decision_queue], ["p0", "p1", "p1", "p2"])
        self.assertEqual(decision_queue[0]["decision_mode"], "阻断加仓")
        self.assertEqual(decision_queue[0]["writes_packet"], "command_center_margin_packet")
        self.assertIn("不能支持加融资", decision_queue[0]["decision_impact"])
        self.assertIn("只检测 margin_detail", decision_queue[0]["recovery_button_context"])
        self.assertEqual(decision_queue[0]["workspace_state_key"], "workspace_mode_v2")
        self.assertEqual(decision_queue[0]["legacy_tab_state_key"], "legacy_workspace_selected_tab")
        self.assertEqual(decision_queue[0]["legacy_tab"], "融资 ETF")
        priority_navigation = snapshot.build_tool_recovery_navigation_state(decision_queue[0])
        self.assertEqual(priority_navigation["workspace_mode_v2"], "高级工具箱（旧版保留）")
        self.assertEqual(priority_navigation["legacy_workspace_selected_tab"], "融资 ETF")
        self.assertEqual(priority_navigation["command_center_last_tool_recovery_policy"], "navigation_only")
        self.assertIn("先处理 P0 阻断交易判断", center["decision_priority_summary"])
        self.assertTrue(all(item["refresh_policy"] == "button_gated" for item in center["actions"]))
        self.assertTrue(all(item["deepseek_called"] is False for item in decision_queue))
        self.assertFalse(center["deepseek_called"])

    def test_legacy_migration_actions_enter_home_recovery_center(self):
        legacy_migration_map = {
            "items": [
                {
                    "key": "margin_etf",
                    "label": "融资 ETF",
                    "completion_status": "partial",
                    "completion_label": "部分完成",
                    "completion_summary": "1/2 项完成条件已满足。",
                    "completion_progress": {
                        "progress_label": "1/2",
                        "target_packet_text": "command_center_etf_packet、command_center_margin_packet",
                        "missing_targets": ["command_center_margin_packet"],
                        "missing_target_text": "command_center_margin_packet",
                    },
                    "migration_state": "wired_waiting_data",
                    "migration_label": "已接 packet，待数据",
                    "tone": "missing",
                    "current_blocker": "融资融券 packet 尚未回流。",
                    "action_label": "打开融资 ETF",
                    "toolbox_entry": "高级工具箱 / 融资 ETF",
                    "workspace_target": "高级工具箱（旧版保留）",
                    "workspace_state_key": "workspace_mode_v2",
                    "legacy_tab_state_key": "legacy_workspace_selected_tab",
                    "legacy_tab": "融资 ETF",
                    "writes_packet": "command_center_etf_packet",
                    "refresh_policy": "button_gated",
                    "deepseek_called": False,
                },
                {
                    "key": "today_pool",
                    "label": "今日关注池",
                    "completion_status": "complete",
                    "completion_label": "迁移完成",
                    "is_complete": True,
                    "writes_packet": "command_center_market_packet",
                },
            ],
            "deepseek_called": False,
        }

        migration_actions = snapshot.build_legacy_migration_recovery_actions_snapshot(legacy_migration_map)
        center = snapshot.build_home_data_recovery_center({"legacy_migration_map": legacy_migration_map})
        migration_action = migration_actions[0]
        center_action = center["actions"][0]
        navigation_state = snapshot.build_tool_recovery_navigation_state(center_action)

        self.assertEqual(len(migration_actions), 1)
        self.assertEqual(migration_action["label"], "融资 ETF")
        self.assertEqual(migration_action["writes_packet"], "command_center_margin_packet")
        self.assertEqual(migration_action["missing_target_text"], "command_center_margin_packet")
        self.assertEqual(migration_action["source_type"], "legacy_migration")
        self.assertEqual(migration_action["refresh_policy"], "button_gated")
        self.assertEqual(center["groups"][4]["key"], "legacy_migration")
        self.assertEqual(center["groups"][4]["count"], 1)
        self.assertEqual(center_action["source_label"], "旧版迁移地图")
        self.assertEqual(center_action["writes_packet"], "command_center_margin_packet")
        self.assertEqual(center["decision_priority_queue"][0]["lane_key"], "p2")
        self.assertEqual(navigation_state["workspace_mode_v2"], "高级工具箱（旧版保留）")
        self.assertEqual(navigation_state["legacy_workspace_selected_tab"], "融资 ETF")
        self.assertEqual(navigation_state["command_center_last_tool_recovery_writes_packet"], "command_center_margin_packet")
        self.assertTrue(all(item["deepseek_called"] is False for item in migration_actions))
        self.assertFalse(center["deepseek_called"])
        json.dumps(center, ensure_ascii=False)

    def test_home_data_recovery_center_attaches_current_recovery_result_statuses(self):
        center = snapshot.build_home_data_recovery_center(
            {
                "data_recovery_actions": [
                    {
                        "label": "融资融券",
                        "status_label": "权限不足",
                        "action_label": "手动刷新融资融券",
                        "writes_packet": "command_center_margin_packet",
                        "refresh_policy": "button_gated",
                    }
                ],
                "data_health_timeline_recovery_actions": [
                    {
                        "label": "筹码/胜率",
                        "status_label": "使用缓存",
                        "action_label": "手动检测筹码/胜率",
                        "writes_packet": "command_center_chip_packet",
                        "legacy_tab": "量化推演",
                        "refresh_policy": "button_gated",
                    }
                ],
                "tool_recovery_actions": [
                    {
                        "label": "下一票雷达",
                        "status_label": "待验证",
                        "action_label": "手动运行下一票雷达",
                        "writes_packet": "command_center_radar_packet",
                        "legacy_tab": "下一票雷达",
                        "refresh_policy": "button_gated",
                    }
                ],
                "command_center_margin_packet": {
                    "status": "ready",
                    "summary": "融资融券已回流",
                    "updated_at": "2026-06-04T10:00:00",
                    "source": "Tushare margin_detail",
                },
                "chip_packet": {
                    "data_status": "cached",
                    "summary": "筹码/胜率使用缓存",
                    "updated_at": "2026-06-03T10:00:00",
                    "source": "Tushare cyq_perf",
                },
                "command_center_radar_packet": {
                    "status": "failed",
                    "data_status": "permission_denied",
                    "status_label": "权限不足",
                    "updated_at": "2026-06-04T10:02:00",
                    "source": "下一票雷达",
                },
            }
        )
        by_label = {item["label"]: item for item in center["actions"]}
        queue_by_label = {item["label"]: item for item in center["decision_priority_queue"]}

        self.assertEqual(by_label["融资融券"]["recovery_result_status"], "recovered")
        self.assertEqual(by_label["融资融券"]["recovery_result_status_label"], "已回流")
        self.assertEqual(by_label["融资融券"]["recovery_result_updated_at"], "2026-06-04T10:00:00")
        self.assertEqual(by_label["筹码/胜率"]["recovery_result_status"], "cached")
        self.assertEqual(by_label["筹码/胜率"]["recovery_result_status_label"], "使用缓存")
        self.assertIn("缓存", by_label["筹码/胜率"]["recovery_result_message"])
        self.assertEqual(by_label["下一票雷达"]["recovery_result_status"], "blocked")
        self.assertEqual(by_label["下一票雷达"]["recovery_result_status_label"], "权限不足")
        self.assertIn("不能把缺失数据当成安全信号", by_label["下一票雷达"]["recovery_result_message"])
        self.assertEqual(queue_by_label["融资融券"]["recovery_result_status_label"], "已回流")
        self.assertEqual(queue_by_label["筹码/胜率"]["recovery_result_status_label"], "使用缓存")
        self.assertEqual(queue_by_label["下一票雷达"]["recovery_result_status_label"], "权限不足")
        self.assertTrue(all(item["recovery_result_external_call_policy"] == "not_triggered" for item in center["actions"]))
        self.assertFalse(center["deepseek_called"])
        json.dumps(center, ensure_ascii=False)

    def test_recovery_priority_lanes_classify_session_skip_cache_and_legacy(self):
        lanes = snapshot.build_recovery_priority_lanes(
            [
                {
                    "label": "涨跌停/情绪",
                    "status": "disabled_this_session",
                    "status_label": "本会话跳过",
                    "source_type": "data_source",
                    "refresh_policy": "button_gated",
                },
                {
                    "label": "筹码/胜率",
                    "status": "empty_recent",
                    "status_label": "近期无数据",
                    "source_type": "a_share",
                    "refresh_policy": "button_gated",
                },
                {
                    "label": "量化推演",
                    "status": "waiting",
                    "source_type": "legacy_tool",
                    "refresh_policy": "button_gated",
                },
            ]
        )
        lane_by_key = {item["key"]: item for item in lanes}

        self.assertEqual(lane_by_key["p0"]["count"], 1)
        self.assertEqual(lane_by_key["p1"]["count"], 1)
        self.assertEqual(lane_by_key["p2"]["count"], 1)
        self.assertIn("权限", lane_by_key["p0"]["next_action"])
        self.assertIn("缓存", lane_by_key["p1"]["next_action"])
        self.assertIn("旧工作台", lane_by_key["p2"]["next_action"])

    def test_recovery_priority_lanes_feed_home_risk_alerts(self):
        center = snapshot.build_home_data_recovery_center(
            {
                "data_recovery_actions": [
                    {
                        "label": "融资融券",
                        "status_label": "权限不足",
                        "priority": 1,
                        "action_label": "手动刷新融资融券",
                        "writes_packet": "command_center_margin_packet",
                        "refresh_policy": "button_gated",
                    }
                ],
                "a_share_user_data_diagnostic": {
                    "recovery_actions": [
                        {
                            "key": "chip_radar",
                            "label": "筹码 / 胜率",
                            "status_label": "暂无当日数据",
                            "action_label": "检测筹码/胜率",
                            "writes_packet": "command_center_chip_packet",
                            "refresh_policy": "button_gated",
                        }
                    ]
                },
                "tool_recovery_actions": [
                    {
                        "key": "next_ticket_radar",
                        "label": "下一票雷达",
                        "status": "waiting",
                        "data_status": "missing",
                        "action_label": "手动运行下一票雷达",
                        "writes_packet": "command_center_radar_packet",
                        "refresh_policy": "button_gated",
                    }
                ],
            }
        )
        alerts = snapshot.attach_recovery_priority_risk_alerts(
            {
                "must_not_do": ["不追高"],
                "reduce_conditions": [],
                "data_gaps": ["暂无显式数据缺口"],
                "uses_cache": False,
            },
            center,
        )
        dumped = json.dumps(alerts, ensure_ascii=False)

        self.assertEqual([item["key"] for item in alerts["recovery_priority_items"]], ["p0", "p1", "p2"])
        self.assertIn("P0 数据能力未恢复前", alerts["must_not_do"][0])
        self.assertTrue(alerts["uses_cache"])
        self.assertFalse(alerts["deepseek_called"])
        self.assertIn("P0 权限/本会话跳过", dumped)
        self.assertIn("P1 缓存/近期无数据", dumped)
        self.assertIn("P2 旧工具 packet 迁移", dumped)
        self.assertIn("融资融券", dumped)
        self.assertIn("筹码", dumped)
        self.assertIn("下一票雷达", dumped)

    def test_home_data_recovery_center_accepts_legacy_a_share_fact_actions(self):
        center = snapshot.build_home_data_recovery_center(
            {
                "legacy_a_share_fact_recovery_actions": [
                    {
                        "key": "legacy_a_share_fact:dragon_tiger",
                        "label": "龙虎榜",
                        "state": "failed",
                        "status_label": "受限/失败",
                        "priority": 1,
                        "reason": "龙虎榜受限/失败；需手动检查权限、积分或网络。",
                        "action_label": "手动刷新龙虎榜",
                        "toolbox_entry": "高级工具箱 / 下一票雷达 / 龙虎榜",
                        "legacy_tab": "下一票雷达",
                        "writes_packet": "command_center_dragon_tiger_packet",
                        "refresh_policy": "button_gated",
                        "deepseek_called": False,
                    }
                ],
            }
        )

        self.assertEqual(center["action_count"], 1)
        self.assertEqual(center["actions"][0]["source_type"], "a_share_fact")
        self.assertEqual(center["actions"][0]["source_label"], "旧版 A股事实卡")
        self.assertEqual(center["actions"][0]["legacy_tab"], "下一票雷达")
        self.assertEqual(center["actions"][0]["writes_packet"], "command_center_dragon_tiger_packet")
        self.assertIn("仍需核对接口状态", center["actions"][0]["diagnostic_answer"])
        self.assertIn("手动刷新龙虎榜", center["summary"])
        navigation_state = snapshot.build_tool_recovery_navigation_state(center["actions"][0])
        self.assertEqual(navigation_state["workspace_mode_v2"], "高级工具箱（旧版保留）")
        self.assertEqual(navigation_state["legacy_workspace_selected_tab"], "下一票雷达")
        self.assertEqual(navigation_state["command_center_last_tool_recovery_writes_packet"], "command_center_dragon_tiger_packet")
        self.assertFalse(center["deepseek_called"])

    def test_home_snapshot_routes_legacy_a_share_fact_actions_to_recovery_center(self):
        today = _dt.date.today().isoformat()
        payload = snapshot.build_home_action_snapshot(
            {
                "command_center_decision_packet": {
                    "status": "ready",
                    "overall_action": "等待",
                    "updated_at": f"{today}T10:00:00",
                }
            },
            target="002008.SZ",
            now=f"{today}T10:02:00",
        )

        fact_actions = payload["legacy_a_share_fact_recovery_actions"]
        center = payload["data_recovery_center"]
        group_counts = {item["key"]: item["count"] for item in center["groups"]}
        dumped = json.dumps(center, ensure_ascii=False)

        self.assertEqual(len(fact_actions), 5)
        self.assertEqual(group_counts["a_share_fact"], 5)
        self.assertIn("旧版 A股事实卡", dumped)
        self.assertIn("command_center_dragon_tiger_packet", json.dumps(fact_actions, ensure_ascii=False))
        self.assertIn("legacy_workspace_selected_tab", json.dumps(fact_actions, ensure_ascii=False))
        self.assertIn("下一票雷达", {item["legacy_tab"] for item in fact_actions})
        self.assertIn("融资 ETF", {item["legacy_tab"] for item in fact_actions})
        self.assertIn("数据源体检", {item["legacy_tab"] for item in fact_actions})
        first_fact_action = next(item for item in center["actions"] if item["source_type"] == "a_share_fact")
        navigation_state = snapshot.build_tool_recovery_navigation_state(first_fact_action)
        self.assertEqual(navigation_state["workspace_mode_v2"], "高级工具箱（旧版保留）")
        self.assertTrue(navigation_state["legacy_workspace_selected_tab"])
        self.assertTrue(all(item["refresh_policy"] == "button_gated" for item in fact_actions))
        self.assertTrue(all(item["deepseek_called"] is False for item in fact_actions))
        self.assertFalse(center["deepseek_called"])

    def test_home_snapshot_builds_tool_recovery_actions_for_missing_old_tools(self):
        today = _dt.date.today().isoformat()
        payload = snapshot.build_home_action_snapshot(
            {
                "command_center_decision_packet": {
                    "status": "ready",
                    "overall_action": "等待",
                    "updated_at": f"{today}T10:00:00",
                }
            },
            target="002008.SZ",
            now=f"{today}T10:02:00",
        )

        actions = payload["tool_recovery_actions"]
        labels = {item["label"] for item in actions}
        writes_packets = {item["writes_packet"] for item in actions}
        dumped = json.dumps(actions, ensure_ascii=False)

        self.assertEqual(len(actions), 4)
        self.assertIn("下一票雷达", labels)
        self.assertIn("融资 ETF", labels)
        self.assertIn("交易纪律/回测", labels)
        self.assertIn("量化推演", labels)
        self.assertIn("command_center_radar_packet", writes_packets)
        self.assertIn("command_center_etf_packet", writes_packets)
        self.assertIn("command_center_discipline_packet", writes_packets)
        self.assertIn("command_center_quant_packet", writes_packets)
        self.assertIn("高级工具箱", dumped)
        self.assertIn("页面打开不会自动全市场扫描", dumped)
        self.assertTrue(all(item["workspace_target"] == "高级工具箱（旧版保留）" for item in actions))
        self.assertTrue(all(item["workspace_state_key"] == "workspace_mode_v2" for item in actions))
        self.assertTrue(all(item["legacy_tab_state_key"] == "legacy_workspace_selected_tab" for item in actions))
        self.assertIn("下一票雷达", {item["legacy_tab"] for item in actions})
        self.assertIn("主导航切到高级工具箱", dumped)
        self.assertTrue(all(item["refresh_policy"] == "button_gated" for item in actions))
        self.assertTrue(all(item["deepseek_called"] is False for item in actions))

        radar_action = next(item for item in actions if item["label"] == "下一票雷达")
        navigation_state = snapshot.build_tool_recovery_navigation_state(radar_action)
        self.assertEqual(navigation_state["workspace_mode_v2"], "高级工具箱（旧版保留）")
        self.assertEqual(navigation_state["legacy_workspace_selected_tab"], "下一票雷达")
        self.assertEqual(navigation_state["command_center_last_tool_recovery_policy"], "navigation_only")
        self.assertEqual(navigation_state["command_center_last_tool_recovery_target_tab"], "下一票雷达")
        self.assertEqual(navigation_state["command_center_last_tool_recovery_writes_packet"], "command_center_radar_packet")

    def test_tool_recovery_navigation_state_is_safe_for_empty_action(self):
        self.assertEqual(snapshot.build_tool_recovery_navigation_state({}), {})
        self.assertEqual(snapshot.build_tool_recovery_navigation_state(object()), {})

    def test_tool_recovery_context_notice_describes_navigation_only(self):
        state = {
            "command_center_last_tool_recovery_label": "下一票雷达",
            "command_center_last_tool_recovery_writes_packet": "command_center_radar_packet",
            "command_center_last_tool_recovery_policy": "navigation_only",
            "legacy_workspace_selected_tab": "下一票雷达",
        }

        notice = snapshot.build_tool_recovery_context_notice(state, selected_tab="下一票雷达")

        self.assertEqual(notice["title"], "来自首页恢复队列")
        self.assertEqual(notice["label"], "下一票雷达")
        self.assertEqual(notice["selected_tab"], "下一票雷达")
        self.assertEqual(notice["target_tab"], "下一票雷达")
        self.assertTrue(notice["is_target_tab"])
        self.assertEqual(notice["writes_packet"], "command_center_radar_packet")
        self.assertIn("手动点击", notice["message"])
        self.assertIn("不会自动运行", notice["action_hint"])
        self.assertEqual(notice["external_call_policy"], "not_triggered")
        self.assertFalse(notice["deepseek_called"])

    def test_tool_recovery_context_notice_warns_when_user_switches_wrong_tab(self):
        state = {
            "command_center_last_tool_recovery_label": "融资融券",
            "command_center_last_tool_recovery_writes_packet": "command_center_margin_packet",
            "command_center_last_tool_recovery_target_tab": "融资 ETF",
            "command_center_last_tool_recovery_policy": "navigation_only",
            "legacy_workspace_selected_tab": "下一票雷达",
        }

        notice = snapshot.build_tool_recovery_context_notice(state, selected_tab="下一票雷达")

        self.assertEqual(notice["selected_tab"], "下一票雷达")
        self.assertEqual(notice["target_tab"], "融资 ETF")
        self.assertFalse(notice["is_target_tab"])
        self.assertIn("请先切回", notice["message"])
        self.assertIn("当前模块不会显示该恢复按钮", notice["action_hint"])
        self.assertEqual(notice["external_call_policy"], "not_triggered")
        self.assertFalse(notice["deepseek_called"])

    def test_tool_recovery_context_notice_ignores_non_navigation_policy(self):
        self.assertEqual(snapshot.build_tool_recovery_context_notice({}), {})
        self.assertEqual(
            snapshot.build_tool_recovery_context_notice(
                {"command_center_last_tool_recovery_policy": "auto_run", "legacy_workspace_selected_tab": "下一票雷达"}
            ),
            {},
        )

    def test_tool_recovery_manual_check_hint_maps_a_share_packets(self):
        hint = snapshot.build_tool_recovery_manual_check_hint(
            {
                "command_center_last_tool_recovery_label": "融资融券",
                "command_center_last_tool_recovery_writes_packet": "command_center_margin_packet",
                "command_center_last_tool_recovery_policy": "navigation_only",
                "legacy_workspace_selected_tab": "融资 ETF",
            },
            selected_tab="融资 ETF",
        )

        self.assertTrue(hint["available"])
        self.assertEqual(hint["check_key"], "margin")
        self.assertEqual(hint["button_label"], "手动检测融资融券")
        self.assertEqual(hint["writes_packet"], "command_center_margin_packet")
        self.assertEqual(hint["external_call_policy"], "button_gated")
        self.assertIn("不自动运行 DeepSeek", hint["help_text"])
        self.assertFalse(hint["deepseek_called"])

    def test_tool_recovery_manual_check_hint_waits_for_target_tab(self):
        hint = snapshot.build_tool_recovery_manual_check_hint(
            {
                "command_center_last_tool_recovery_label": "融资融券",
                "command_center_last_tool_recovery_writes_packet": "command_center_margin_packet",
                "command_center_last_tool_recovery_target_tab": "融资 ETF",
                "command_center_last_tool_recovery_policy": "navigation_only",
                "legacy_workspace_selected_tab": "下一票雷达",
            },
            selected_tab="下一票雷达",
        )

        self.assertFalse(hint["available"])
        self.assertEqual(hint["target_tab"], "融资 ETF")
        self.assertIn("请先切回", hint["message"])
        self.assertEqual(hint["external_call_policy"], "not_triggered")
        self.assertFalse(hint["deepseek_called"])

    def test_tool_recovery_manual_check_hint_keeps_unknown_packet_manual(self):
        hint = snapshot.build_tool_recovery_manual_check_hint(
            {
                "command_center_last_tool_recovery_label": "旧工具",
                "command_center_last_tool_recovery_writes_packet": "command_center_unknown_packet",
                "command_center_last_tool_recovery_policy": "navigation_only",
                "legacy_workspace_selected_tab": "今日关注池",
            },
            selected_tab="今日关注池",
        )

        self.assertFalse(hint["available"])
        self.assertEqual(hint["writes_packet"], "command_center_unknown_packet")
        self.assertEqual(hint["external_call_policy"], "not_triggered")
        self.assertIn("还没有绑定单项检测按钮", hint["message"])
        self.assertFalse(hint["deepseek_called"])

    def test_tool_recovery_result_notice_waits_for_packet(self):
        notice = snapshot.build_tool_recovery_result_notice(
            {
                "command_center_last_tool_recovery_label": "下一票雷达",
                "command_center_last_tool_recovery_writes_packet": "command_center_radar_packet",
                "command_center_last_tool_recovery_policy": "navigation_only",
                "legacy_workspace_selected_tab": "下一票雷达",
            },
            selected_tab="下一票雷达",
        )

        self.assertEqual(notice["status"], "waiting")
        self.assertIn("尚未检测到", notice["message"])
        self.assertEqual(notice["external_call_policy"], "not_triggered")
        self.assertFalse(notice["deepseek_called"])

    def test_tool_recovery_result_notice_waits_for_target_tab(self):
        notice = snapshot.build_tool_recovery_result_notice(
            {
                "command_center_last_tool_recovery_label": "融资融券",
                "command_center_last_tool_recovery_writes_packet": "command_center_margin_packet",
                "command_center_last_tool_recovery_target_tab": "融资 ETF",
                "command_center_last_tool_recovery_policy": "navigation_only",
                "legacy_workspace_selected_tab": "下一票雷达",
                "command_center_margin_packet": {"status": "ready", "summary": "已刷新融资融券"},
            },
            selected_tab="下一票雷达",
        )

        self.assertEqual(notice["status"], "waiting")
        self.assertEqual(notice["title"], "恢复入口不在当前模块")
        self.assertEqual(notice["target_tab"], "融资 ETF")
        self.assertIn("请切回", notice["next_action"])
        self.assertEqual(notice["external_call_policy"], "not_triggered")
        self.assertFalse(notice["deepseek_called"])

    def test_tool_recovery_result_notice_detects_recovered_packet(self):
        notice = snapshot.build_tool_recovery_result_notice(
            {
                "command_center_last_tool_recovery_label": "下一票雷达",
                "command_center_last_tool_recovery_writes_packet": "command_center_radar_packet",
                "command_center_last_tool_recovery_policy": "navigation_only",
                "legacy_workspace_selected_tab": "下一票雷达",
                "command_center_radar_packet": {
                    "status": "ready",
                    "source": "下一票雷达本地缓存",
                    "generated_at": "2026-06-03T10:00:00",
                    "top_candidates": [{"ticker": "002008.SZ", "name": "大族激光"}],
                },
            },
            selected_tab="下一票雷达",
        )

        self.assertEqual(notice["status"], "recovered")
        self.assertIn("已写入 command_center_radar_packet", notice["message"])
        self.assertEqual(notice["source"], "下一票雷达本地缓存")
        self.assertEqual(notice["updated_at"], "2026-06-03T10:00:00")
        self.assertEqual(notice["external_call_policy"], "not_triggered")
        self.assertFalse(notice["deepseek_called"])

    def test_tool_recovery_result_notice_reports_blocked_packet(self):
        notice = snapshot.build_tool_recovery_result_notice(
            {
                "command_center_last_tool_recovery_label": "龙虎榜",
                "command_center_last_tool_recovery_writes_packet": "command_center_dragon_tiger_packet",
                "command_center_last_tool_recovery_policy": "navigation_only",
                "legacy_workspace_selected_tab": "下一票雷达",
                "command_center_dragon_tiger_packet": {
                    "status": "failed",
                    "data_status": "permission_denied",
                    "summary": "Tushare top_list 当前权限不足。",
                    "updated_at": "2026-06-03T10:00:00",
                    "source": "Tushare top_list",
                },
            },
            selected_tab="下一票雷达",
        )

        self.assertEqual(notice["status"], "blocked")
        self.assertIn("仍未形成可用回流", notice["message"])
        self.assertIn("权限不足", notice["message"])
        self.assertIn("不要把缺失数据当作利好", notice["next_action"])
        self.assertEqual(notice["source"], "Tushare top_list")
        self.assertEqual(notice["external_call_policy"], "not_triggered")
        self.assertFalse(notice["deepseek_called"])

    def test_tool_recovery_result_notice_treats_cached_packet_as_recovered(self):
        notice = snapshot.build_tool_recovery_result_notice(
            {
                "command_center_last_tool_recovery_label": "个股资金流",
                "command_center_last_tool_recovery_writes_packet": "command_center_moneyflow_packet",
                "command_center_last_tool_recovery_policy": "navigation_only",
                "legacy_workspace_selected_tab": "今日关注池",
                "command_center_moneyflow_packet": {
                    "data_status": "cached",
                    "summary": "资金流缓存已读取。",
                    "updated_at": "2026-06-03T10:00:00",
                },
            },
            selected_tab="今日关注池",
        )

        self.assertEqual(notice["status"], "recovered")
        self.assertIn("已写入 command_center_moneyflow_packet", notice["message"])
        self.assertEqual(notice["external_call_policy"], "not_triggered")
        self.assertFalse(notice["deepseek_called"])

    def test_a_share_diagnostic_recovery_result_notice_detects_recovered_packet(self):
        notice = snapshot.build_a_share_diagnostic_recovery_result_notice(
            {
                "command_center_last_a_share_diagnostic_recovery_result": {
                    "label": "个股资金流",
                    "writes_packet": "command_center_moneyflow_packet",
                    "capability_state": "available",
                    "status_label": "可用",
                    "message": "已读取到最近资金流数据。",
                    "checked_at": "2026-06-03T10:00:00",
                    "api_hint": "Tushare moneyflow",
                    "deepseek_called": False,
                },
                "command_center_moneyflow_packet": {
                    "status": "ready",
                    "summary": "资金流已回流",
                    "updated_at": "2026-06-03T10:00:00",
                },
            }
        )

        self.assertEqual(notice["status"], "recovered")
        self.assertEqual(notice["tone"], "ready")
        self.assertIn("个股资金流", notice["message"])
        self.assertEqual(notice["writes_packet"], "command_center_moneyflow_packet")
        self.assertEqual(notice["external_call_policy"], "button_gated")
        self.assertFalse(notice["deepseek_called"])

    def test_a_share_diagnostic_recovery_result_notice_reports_blocked_state(self):
        notice = snapshot.build_a_share_diagnostic_recovery_result_notice(
            {
                "command_center_last_a_share_diagnostic_recovery_result": {
                    "label": "龙虎榜",
                    "writes_packet": "command_center_dragon_tiger_packet",
                    "capability_state": "permission_denied",
                    "status_label": "权限不足",
                    "message": "当前接口权限不足。",
                    "checked_at": "2026-06-03T10:05:00",
                    "api_hint": "Tushare top_list / top_inst",
                    "deepseek_called": False,
                }
            }
        )

        self.assertEqual(notice["status"], "blocked")
        self.assertEqual(notice["tone"], "failed")
        self.assertIn("权限不足", notice["message"])
        self.assertIn("权限", notice["next_action"])
        self.assertEqual(notice["external_call_policy"], "button_gated")
        self.assertFalse(notice["deepseek_called"])

    def test_latest_recovery_result_notice_prefers_manual_detection_result(self):
        notice = snapshot.build_latest_recovery_result_notice(
            {
                "command_center_last_a_share_diagnostic_recovery_result": {
                    "label": "涨跌停/情绪",
                    "writes_packet": "command_center_limit_emotion_packet",
                    "capability_state": "permission_denied",
                    "status_label": "权限不足",
                    "message": "limit_cpt_list 权限不足。",
                    "checked_at": "2026-06-03T10:05:00",
                    "api_hint": "Tushare limit_cpt_list",
                    "deepseek_called": False,
                },
                "command_center_last_tool_recovery_label": "下一票雷达",
                "command_center_last_tool_recovery_writes_packet": "command_center_radar_packet",
                "command_center_last_tool_recovery_policy": "navigation_only",
            }
        )

        self.assertEqual(notice["source_type"], "a_share_diagnostic")
        self.assertEqual(notice["status"], "blocked")
        self.assertEqual(notice["tone"], "failed")
        self.assertEqual(notice["writes_packet"], "command_center_limit_emotion_packet")
        self.assertIn("Tushare 之前拉满不等于今天一定可见", notice["why_not_found"])
        self.assertIn("只检测 stk_limit / limit_list_d / limit_cpt_list", notice["button_context"])
        self.assertIn("缺少涨跌停/情绪", notice["decision_guardrail"])
        self.assertTrue(notice["manual_recovery_steps"])
        self.assertEqual(notice["external_call_policy"], "button_gated")
        self.assertFalse(notice["deepseek_called"])

    def test_latest_recovery_result_notice_can_prefer_latest_tool_recovery(self):
        notice = snapshot.build_latest_recovery_result_notice(
            {
                "command_center_last_recovery_result_source": "tool_recovery",
                "command_center_last_a_share_diagnostic_recovery_result": {
                    "label": "涨跌停/情绪",
                    "writes_packet": "command_center_limit_emotion_packet",
                    "capability_state": "permission_denied",
                    "status_label": "权限不足",
                    "message": "limit_cpt_list 权限不足。",
                    "checked_at": "2026-06-03T10:05:00",
                    "api_hint": "Tushare limit_cpt_list",
                    "deepseek_called": False,
                },
                "command_center_last_tool_recovery_label": "下一票雷达",
                "command_center_last_tool_recovery_writes_packet": "command_center_radar_packet",
                "command_center_last_tool_recovery_target_tab": "下一票雷达",
                "command_center_last_tool_recovery_policy": "navigation_only",
                "legacy_workspace_selected_tab": "下一票雷达",
                "command_center_radar_packet": {
                    "status": "ready",
                    "top_candidates": [{"ticker": "002008.SZ", "name": "大族激光"}],
                    "generated_at": "2026-06-03T10:10:00",
                    "source": "下一票雷达本地缓存",
                },
            },
            selected_tab="下一票雷达",
        )

        self.assertEqual(notice["source_type"], "tool_recovery")
        self.assertEqual(notice["status"], "recovered")
        self.assertEqual(notice["writes_packet"], "command_center_radar_packet")
        self.assertIn("下一票雷达", notice["message"])
        self.assertFalse(notice["deepseek_called"])

    def test_latest_recovery_result_notice_explains_chip_gap_after_manual_check(self):
        notice = snapshot.build_latest_recovery_result_notice(
            {
                "command_center_last_a_share_diagnostic_recovery_result": {
                    "label": "筹码/胜率",
                    "writes_packet": "command_center_chip_packet",
                    "capability_state": "empty_recent",
                    "status_label": "近期无数据",
                    "message": "近 30 日暂无 cyq_perf/cyq_chips 可验证数据。",
                    "checked_at": "2026-06-03T10:05:00",
                    "api_hint": "Tushare cyq_perf/cyq_chips",
                    "deepseek_called": False,
                }
            }
        )

        self.assertEqual(notice["source_type"], "a_share_diagnostic")
        self.assertEqual(notice["status"], "waiting")
        self.assertEqual(notice["tone"], "stale")
        self.assertIn("cyq_perf 或 cyq_chips 权限", notice["why_not_found"])
        self.assertIn("只检测 cyq_perf / cyq_chips", notice["button_context"])
        self.assertIn("缺少筹码/胜率", notice["decision_guardrail"])
        self.assertIn("command_center_chip_packet", notice["manual_recovery_steps"][-1])
        self.assertEqual(notice["external_call_policy"], "button_gated")
        self.assertFalse(notice["deepseek_called"])

    def test_home_snapshot_includes_latest_recovery_result_notice(self):
        today = _dt.date.today().isoformat()
        payload = snapshot.build_home_action_snapshot(
            {
                "command_center_decision_packet": {
                    "status": "ready",
                    "overall_action": "等待",
                    "updated_at": f"{today}T10:00:00",
                },
                "command_center_last_a_share_diagnostic_recovery_result": {
                    "label": "个股资金流",
                    "writes_packet": "command_center_moneyflow_packet",
                    "capability_state": "available",
                    "status_label": "可用",
                    "message": "已读取到最近资金流数据。",
                    "checked_at": f"{today}T10:05:00",
                    "api_hint": "Tushare moneyflow",
                    "deepseek_called": False,
                },
                "command_center_moneyflow_packet": {
                    "status": "ready",
                    "summary": "资金流已回流",
                    "updated_at": f"{today}T10:05:00",
                },
            },
            target="002008.SZ",
            now=f"{today}T10:06:00",
        )

        notice = payload["latest_recovery_result_notice"]
        self.assertEqual(notice["status"], "recovered")
        self.assertEqual(notice["source_type"], "a_share_diagnostic")
        self.assertEqual(notice["writes_packet"], "command_center_moneyflow_packet")
        self.assertIn("Home Action Snapshot", notice["next_action"])
        self.assertFalse(notice["deepseek_called"])

    def test_recovery_result_status_strip_detects_recovered_packet(self):
        strip = snapshot.build_recovery_result_status_strip(
            {
                "latest_recovery_result_notice": {
                    "status": "recovered",
                    "label": "个股资金流",
                    "writes_packet": "command_center_moneyflow_packet",
                    "source": "Tushare moneyflow",
                    "updated_at": "2026-06-03T10:00:00",
                    "next_action": "返回综合中心复核。",
                },
                "command_center_moneyflow_packet": {
                    "status": "ready",
                    "summary": "资金流已回流",
                    "updated_at": "2026-06-03T10:00:00",
                    "source": "Tushare moneyflow",
                },
            }
        )

        self.assertEqual(strip["status"], "recovered")
        self.assertEqual(strip["tone"], "ready")
        self.assertIn("已回流", strip["headline"])
        self.assertEqual(strip["items"][0]["status_label"], "已回流")
        self.assertEqual(strip["items"][0]["packet_key"], "command_center_moneyflow_packet")
        self.assertFalse(strip["deepseek_called"])
        json.dumps(strip, ensure_ascii=False)

    def test_recovery_result_status_strip_detects_cached_snapshot_packet(self):
        strip = snapshot.build_recovery_result_status_strip(
            {
                "latest_recovery_result_notice": {
                    "status": "recovered",
                    "label": "下一票雷达",
                    "writes_packet": "command_center_radar_packet",
                },
                "radar_packet": {
                    "data_status": "cached",
                    "top_candidates": [{"ticker": "002008.SZ"}],
                    "updated_at": "2026-06-03T10:00:00",
                },
            }
        )

        self.assertEqual(strip["status"], "cached")
        self.assertEqual(strip["tone"], "stale")
        self.assertIn("使用缓存", strip["headline"])
        self.assertEqual(strip["items"][0]["packet_key"], "radar_packet")
        self.assertEqual(strip["items"][0]["status_label"], "使用缓存")
        self.assertFalse(strip["items"][0]["deepseek_called"])

    def test_recovery_result_status_strip_waits_when_notice_recovered_but_packet_missing(self):
        strip = snapshot.build_recovery_result_status_strip(
            {
                "latest_recovery_result_notice": {
                    "status": "recovered",
                    "label": "龙虎榜",
                    "writes_packet": "command_center_dragon_tiger_packet",
                    "message": "接口可用，但目标 packet 尚未写回。",
                }
            }
        )

        self.assertEqual(strip["status"], "waiting")
        self.assertEqual(strip["tone"], "stale")
        self.assertEqual(strip["items"][0]["status_label"], "待验证")
        self.assertIn("尚未检测到可读回流", strip["summary"])
        self.assertFalse(strip["deepseek_called"])

    def test_recovery_result_status_strip_reports_permission_block(self):
        strip = snapshot.build_recovery_result_status_strip(
            {
                "latest_recovery_result_notice": {
                    "status": "blocked",
                    "label": "融资融券",
                    "writes_packet": "command_center_margin_packet",
                    "next_action": "检查权限后手动重试。",
                },
                "command_center_margin_packet": {
                    "status": "failed",
                    "data_status": "permission_denied",
                    "status_label": "权限不足",
                    "source": "Tushare margin_detail",
                    "updated_at": "2026-06-03T10:00:00",
                },
            }
        )

        self.assertEqual(strip["status"], "blocked")
        self.assertEqual(strip["tone"], "failed")
        self.assertEqual(strip["items"][0]["status_label"], "权限不足")
        self.assertIn("不能把缺失数据当成安全信号", strip["summary"])
        self.assertEqual(strip["items"][0]["external_call_policy"], "not_triggered")
        self.assertFalse(strip["deepseek_called"])

    def test_recovery_result_timeline_keeps_recent_manual_outcomes(self):
        timeline = snapshot.build_recovery_result_timeline(
            {
                "latest_recovery_result_notice": {
                    "status": "blocked",
                    "label": "融资融券",
                    "writes_packet": "command_center_margin_packet",
                    "source": "Tushare margin_detail",
                    "updated_at": "2026-06-03T10:00:00",
                    "next_action": "检查权限后手动重试。",
                },
                "command_center_margin_packet": {
                    "status": "failed",
                    "data_status": "permission_denied",
                    "status_label": "权限不足",
                    "updated_at": "2026-06-03T10:00:00",
                    "source": "Tushare margin_detail",
                },
                "command_center_recovery_result_timeline": {
                    "items": [
                        {
                            "label": "个股资金流",
                            "writes_packet": "command_center_moneyflow_packet",
                            "packet_key": "command_center_moneyflow_packet",
                            "status": "recovered",
                            "status_label": "已回流",
                            "tone": "ready",
                            "updated_at": "2026-06-03T09:50:00",
                            "source": "Tushare moneyflow",
                        }
                    ]
                },
            }
        )

        self.assertEqual(timeline["title"], "恢复结果时间线")
        self.assertEqual(timeline["status"], "blocked")
        self.assertEqual(timeline["items"][0]["event_type"], "packet_blocked")
        self.assertEqual(timeline["items"][0]["writes_packet"], "command_center_margin_packet")
        self.assertEqual(timeline["items"][1]["event_type"], "packet_recovered")
        self.assertEqual(timeline["status_counts"]["blocked"], 1)
        self.assertEqual(timeline["status_counts"]["recovered"], 1)
        self.assertEqual(timeline["external_call_policy"], "not_triggered")
        self.assertFalse(timeline["deepseek_called"])
        json.dumps(timeline, ensure_ascii=False)

    def test_home_snapshot_includes_recovery_result_status_strip(self):
        today = _dt.date.today().isoformat()
        payload = snapshot.build_home_action_snapshot(
            {
                "command_center_decision_packet": {
                    "status": "ready",
                    "overall_action": "等待",
                    "updated_at": f"{today}T10:00:00",
                },
                "command_center_last_a_share_diagnostic_recovery_result": {
                    "label": "龙虎榜",
                    "writes_packet": "command_center_dragon_tiger_packet",
                    "capability_state": "permission_denied",
                    "status_label": "权限不足",
                    "message": "top_list 权限不足。",
                    "checked_at": f"{today}T10:05:00",
                    "api_hint": "Tushare top_list",
                    "deepseek_called": False,
                },
                "command_center_dragon_tiger_packet": {
                    "status": "failed",
                    "data_status": "permission_denied",
                    "status_label": "权限不足",
                    "updated_at": f"{today}T10:05:00",
                    "source": "Tushare top_list",
                },
            },
            target="002008.SZ",
            now=f"{today}T10:06:00",
        )

        strip = payload["recovery_result_status_strip"]
        self.assertEqual(strip["title"], "最近恢复状态")
        self.assertEqual(strip["status"], "blocked")
        self.assertEqual(strip["items"][0]["writes_packet"], "command_center_dragon_tiger_packet")
        self.assertEqual(strip["items"][0]["status_label"], "权限不足")
        self.assertFalse(strip["deepseek_called"])
        timeline = payload["command_center_recovery_result_timeline"]
        self.assertEqual(timeline["title"], "恢复结果时间线")
        self.assertEqual(timeline["items"][0]["writes_packet"], "command_center_dragon_tiger_packet")
        self.assertEqual(timeline["items"][0]["event_type"], "packet_blocked")
        self.assertEqual(payload["recovery_result_timeline"], timeline)
        self.assertFalse(timeline["deepseek_called"])

    def test_home_snapshot_skips_ready_old_tool_packets_in_recovery_actions(self):
        today = _dt.date.today().isoformat()
        payload = snapshot.build_home_action_snapshot(
            {
                "command_center_decision_packet": {
                    "status": "ready",
                    "overall_action": "等待",
                    "updated_at": f"{today}T10:00:00",
                },
                "command_center_radar_packet": {
                    "status": "ready",
                    "top_candidates": [{"ticker": "002008.SZ", "name": "大族激光", "action_state": "可准备"}],
                },
                "command_center_etf_packet": {
                    "status": "ready",
                    "recommended_etfs": [{"code": "560780.SH", "name": "半导体 ETF", "score": 72}],
                },
                "command_center_discipline_packet": {
                    "status": "ready",
                    "summary": "已读取回测缓存。",
                    "win_rate": 62,
                },
                "command_center_quant_packet": {
                    "status": "ready",
                    "score": 68,
                    "summary": "量化推演已缓存。",
                },
            },
            target="002008.SZ",
            now=f"{today}T10:02:00",
        )

        self.assertEqual(payload["tool_recovery_actions"], [])

    def test_loaded_home_snapshot_keeps_tool_recovery_actions(self):
        today = _dt.date.today().isoformat()
        with tempfile.TemporaryDirectory() as tmp:
            payload = snapshot.build_home_action_snapshot(
                {
                    "command_center_decision_packet": {
                        "status": "ready",
                        "overall_action": "等待",
                        "updated_at": f"{today}T10:00:00",
                    }
                },
                target="002008.SZ",
                now=f"{today}T10:02:00",
            )
            snapshot.save_home_action_snapshot(payload, base_dir=tmp)
            loaded = snapshot.load_home_action_snapshot(base_dir=tmp)

        dumped = json.dumps(loaded["tool_recovery_actions"], ensure_ascii=False)
        self.assertIn("下一票雷达", dumped)
        self.assertIn("融资 ETF", dumped)
        self.assertIn("交易纪律/回测", dumped)
        self.assertIn("量化推演", dumped)
        self.assertIn("legacy_workspace_selected_tab", dumped)
        self.assertIn("主导航切到高级工具箱", dumped)
        self.assertTrue(all(item["refresh_policy"] == "button_gated" for item in loaded["tool_recovery_actions"]))
        self.assertTrue(all(item["deepseek_called"] is False for item in loaded["tool_recovery_actions"]))

    def test_home_snapshot_persists_market_packet(self):
        today = _dt.date.today().isoformat()
        state = {
            "command_center_decision_packet": {
                "status": "ready",
                "overall_action": "等待",
                "updated_at": f"{today}T10:00:00",
            },
            "legacy_market_style_fact_packet": {
                "market_state": "修复",
                "risk_switch": "适合轻仓试错",
                "limit_up_count": 38,
                "limit_down_count": 2,
                "break_limit_count": 6,
                "verified_sources": ["Tushare limit_list_d"],
                "updated_at": f"{today}T10:01:00",
            },
        }

        payload = snapshot.build_home_action_snapshot(state, target="002008.SZ", now=f"{today}T10:02:00")

        self.assertEqual(payload["market_packet"]["market_state"], "修复")
        self.assertEqual(payload["market_packet"]["action_state"], "轻仓验证")
        self.assertEqual(payload["market_packet"]["limit_up_count"], 38)
        self.assertFalse(payload["market_packet"]["deepseek_called"])

    def test_home_snapshot_persists_quant_packet(self):
        today = _dt.date.today().isoformat()
        state = {
            "command_center_decision_packet": {
                "status": "ready",
                "overall_action": "等待",
                "updated_at": f"{today}T10:00:00",
            },
            "legacy_quant_result": {
                "status": "completed",
                "generated_at": f"{today}T10:01:00",
                "target": "002008.SZ",
                "market_type": "A股",
                "score": 68,
                "direction": "偏积极但需验证",
                "summary": "轻量量化摘要已生成。",
            },
        }

        payload = snapshot.build_home_action_snapshot(state, target="002008.SZ", now=f"{today}T10:02:00")

        self.assertEqual(payload["quant_packet"]["data_status"], "ready")
        self.assertEqual(payload["quant_packet"]["score"], 68)
        self.assertEqual(payload["quant_packet"]["action_state"], "轻仓验证")
        self.assertIn(payload["quant_packet"]["decision_brief"]["action_mode"], {"usable_evidence", "verify_quant"})
        self.assertIn("量化", payload["quant_packet"]["decision_brief"]["title"])
        self.assertIn("手动触发", payload["quant_packet"]["manual_required_text"])
        self.assertFalse(payload["quant_packet"]["deepseek_called"])

    def test_home_snapshot_persists_chip_packet(self):
        today = _dt.date.today().isoformat()
        state = {
            "command_center_decision_packet": {
                "status": "ready",
                "overall_action": "等待",
                "updated_at": f"{today}T10:00:00",
            },
            "a_share_professional_facts": {
                "chip_radar": {
                    "available": True,
                    "trade_date": "20260603",
                    "winner_rate": 72,
                    "weight_avg": 23.4,
                    "chip_band_width": 14,
                    "chip_pressure_comment": "获利盘压力偏高。",
                    "updated_at": f"{today}T10:01:00",
                }
            },
        }

        payload = snapshot.build_home_action_snapshot(state, target="002008.SZ", now=f"{today}T10:02:00")

        self.assertEqual(payload["chip_packet"]["data_status"], "ready")
        self.assertEqual(payload["chip_packet"]["winner_rate"], 72)
        self.assertEqual(payload["chip_packet"]["pressure_state"], "获利盘压力偏高")
        self.assertIn("手动刷新", payload["chip_packet"]["manual_required_text"])
        diagnostic_dump = json.dumps(payload["a_share_user_data_diagnostic"], ensure_ascii=False)
        self.assertIn("筹码 / 胜率", diagnostic_dump)
        chip_item = next(item for item in payload["a_share_user_data_diagnostic"]["items"] if item["key"] == "chip_radar")
        self.assertEqual(chip_item["status"], "available")
        self.assertEqual(chip_item["writes_packet"], "command_center_chip_packet")
        self.assertNotIn("command_center_chip_packet", json.dumps(payload["a_share_user_data_diagnostic"]["recovery_actions"], ensure_ascii=False))
        self.assertFalse(payload["chip_packet"]["deepseek_called"])

    def test_home_snapshot_persists_moneyflow_and_dragon_packets(self):
        today = _dt.date.today().isoformat()
        state = {
            "command_center_decision_packet": {
                "status": "ready",
                "overall_action": "等待",
                "updated_at": f"{today}T10:00:00",
            },
            "a_share_professional_facts": {
                "moneyflow": {
                    "available": True,
                    "date": "20260603",
                    "main_net_yi": 1.23,
                    "five_day_main_net_yi": 3.45,
                    "updated_at": f"{today}T10:01:00",
                },
                "dragon_tiger": {
                    "available": True,
                    "latest_date": "20260603",
                    "net_buy_amount_yi": 1.3,
                    "inst_summary": "席位3条，净买入1.3亿",
                    "updated_at": f"{today}T10:01:00",
                },
            },
        }

        payload = snapshot.build_home_action_snapshot(state, target="002008.SZ", now=f"{today}T10:02:00")

        self.assertEqual(payload["moneyflow_packet"]["data_status"], "ready")
        self.assertEqual(payload["moneyflow_packet"]["flow_state"], "主力净流入")
        self.assertEqual(payload["dragon_tiger_packet"]["data_status"], "ready")
        self.assertEqual(payload["dragon_tiger_packet"]["activity_state"], "席位净买入")
        self.assertFalse(payload["moneyflow_packet"]["deepseek_called"])
        self.assertFalse(payload["dragon_tiger_packet"]["deepseek_called"])

    def test_home_snapshot_persists_a_share_evidence_packet(self):
        today = _dt.date.today().isoformat()
        payload = snapshot.build_home_action_snapshot(
            {
                "command_center_decision_packet": {
                    "status": "ready",
                    "overall_action": "等待",
                    "updated_at": f"{today}T10:00:00",
                },
                "command_center_moneyflow_packet": {
                    "status": "ready",
                    "data_status": "ready",
                    "summary": "资金流可用",
                    "flow_state": "主力净流入",
                    "updated_at": f"{today}T10:01:00",
                },
                "command_center_margin_packet": {
                    "status": "partial",
                    "data_status": "cached",
                    "summary": "融资缓存",
                    "updated_at": f"{today}T10:01:00",
                },
                "command_center_hard_risk_packet": {
                    "status": "failed",
                    "data_status": "missing",
                    "summary": "公告权限不足",
                },
            },
            target="002008.SZ",
            now=f"{today}T10:02:00",
        )

        evidence = payload["a_share_evidence_packet"]
        self.assertEqual(evidence, payload["command_center_evidence_radar_packet"])
        self.assertEqual(evidence["title"], "A股证据雷达")
        self.assertEqual(evidence["ready_count"], 1)
        self.assertEqual(evidence["cached_count"], 0)
        self.assertEqual(evidence["failed_count"], 1)
        self.assertEqual(evidence["decision_summary"], "支持 1｜阻断 1｜缓存 0｜缺失 4")
        self.assertEqual(evidence["loop_status"]["label"], "证据闭环")
        self.assertEqual(evidence["loop_status"]["status"], "blocked")
        self.assertEqual(evidence["loop_status"]["tone"], "failed")
        self.assertEqual(evidence["loop_status"]["summary"], "支持 1｜阻断 1｜缓存 0｜缺失 4")
        self.assertFalse(evidence["loop_status"]["deepseek_called"])
        self.assertEqual(evidence["core_evidence_action_brief"]["status"], "partial")
        self.assertIn("核心证据", evidence["core_evidence_action_brief"]["title"])
        self.assertIn("待补", evidence["core_evidence_action_brief"]["summary"])
        self.assertFalse(evidence["core_evidence_action_brief"]["deepseek_called"])
        core = {item["key"]: item for item in evidence["core_evidence_items"]}
        self.assertEqual(list(core), ["dragon_tiger", "margin", "limit_emotion"])
        self.assertEqual(core["margin"]["writes_packet"], "command_center_margin_packet")
        self.assertEqual(core["dragon_tiger"]["legacy_tab"], "下一票雷达")
        self.assertEqual(core["limit_emotion"]["writes_packet"], "command_center_limit_emotion_packet")
        self.assertIn("龙虎榜", json.dumps(evidence["core_evidence_items"], ensure_ascii=False))
        self.assertIn("已刷新", evidence["core_evidence_summary"])
        self.assertIn("command_center_moneyflow_packet", json.dumps(evidence, ensure_ascii=False))
        self.assertFalse(evidence["deepseek_called"])
        json.dumps(payload, ensure_ascii=False)

    def test_a_share_fact_recovery_summary_counts_packet_states(self):
        summary = snapshot.build_a_share_fact_recovery_summary(
            {
                "moneyflow_packet": {
                    "status": "ready",
                    "data_status": "ready",
                    "recovery_state": "recovered",
                    "status_label": "可用",
                    "source": "Tushare moneyflow",
                    "updated_at": "2026-06-04T10:00:00",
                },
                "dragon_tiger_packet": {
                    "status": "failed",
                    "capability_state": "permission_denied",
                    "recovery_state": "blocked",
                    "status_label": "权限不足",
                    "source": "Tushare top_list",
                },
                "margin_packet": {
                    "status": "waiting",
                    "capability_state": "empty_recent",
                    "recovery_state": "waiting",
                    "status_label": "近期无数据",
                },
            }
        )

        self.assertEqual(summary["total_count"], 5)
        self.assertEqual(summary["recovered_count"], 1)
        self.assertEqual(summary["blocked_count"], 1)
        self.assertEqual(summary["waiting_count"], 3)
        self.assertIn("已回流 1", summary["summary"])
        self.assertIn("仍受限 1", summary["summary"])
        self.assertEqual(summary["tone"], "failed")
        by_key = {item["key"]: item for item in summary["items"]}
        self.assertEqual(by_key["moneyflow"]["packet_status_text"], "已回流｜可用｜command_center_moneyflow_packet")
        self.assertEqual(by_key["dragon_tiger"]["action_label"], "手动检测龙虎榜")
        self.assertIn("回流 command_center_dragon_tiger_packet", by_key["dragon_tiger"]["next_action"])
        self.assertIn("不能把缺失数据当成利好", by_key["dragon_tiger"]["diagnostic_answer"])
        self.assertEqual(by_key["dragon_tiger"]["legacy_tab"], "下一票雷达")
        self.assertEqual(by_key["dragon_tiger"]["workspace_state_key"], "workspace_mode_v2")
        self.assertEqual(by_key["dragon_tiger"]["legacy_tab_state_key"], "legacy_workspace_selected_tab")
        self.assertEqual(by_key["dragon_tiger"]["refresh_policy"], "button_gated")
        self.assertIn("高级工具箱", by_key["dragon_tiger"]["navigation_label"])
        navigation_state = snapshot.build_tool_recovery_navigation_state(by_key["dragon_tiger"])
        self.assertEqual(navigation_state["workspace_mode_v2"], "高级工具箱（旧版保留）")
        self.assertEqual(navigation_state["legacy_workspace_selected_tab"], "下一票雷达")
        self.assertIn("页面打开不会自动请求 Tushare", by_key["margin"]["next_action"])
        self.assertFalse(summary["deepseek_called"])
        json.dumps(summary, ensure_ascii=False)

    def test_a_share_evidence_recovery_ledger_explains_decision_impact(self):
        ledger = snapshot.build_a_share_evidence_recovery_ledger(
            {
                "moneyflow_packet": {
                    "status": "ready",
                    "data_status": "ready",
                    "recovery_state": "recovered",
                    "status_label": "可用",
                    "source": "Tushare moneyflow",
                    "updated_at": "2026-06-04T10:00:00",
                },
                "dragon_tiger_packet": {
                    "status": "failed",
                    "capability_state": "permission_denied",
                    "recovery_state": "blocked",
                    "status_label": "权限不足",
                    "source": "Tushare top_list",
                },
            }
        )
        by_key = {item["key"]: item for item in ledger["items"]}

        self.assertEqual(ledger["title"], "A股证据回流总账")
        self.assertEqual(ledger["status"], "blocked")
        self.assertEqual(ledger["recovered_count"], 1)
        self.assertEqual(ledger["blocked_count"], 1)
        self.assertIn("已回流 1", ledger["summary"])
        self.assertIn("仍受限 1", ledger["summary"])
        self.assertEqual(by_key["moneyflow"]["ledger_label"], "已回流")
        self.assertIn("可进入证据链", by_key["moneyflow"]["decision_impact"])
        self.assertIn("阻断加仓", by_key["dragon_tiger"]["decision_impact"])
        self.assertEqual(by_key["dragon_tiger"]["writes_packet"], "command_center_dragon_tiger_packet")
        self.assertIn("高级工具箱", by_key["dragon_tiger"]["toolbox_entry"])
        self.assertFalse(ledger["deepseek_called"])
        self.assertEqual(ledger["external_call_policy"], "not_triggered")
        json.dumps(ledger, ensure_ascii=False)

    def test_strategy_prerequisite_recovery_ledger_explains_quant_and_discipline_impact(self):
        ledger = snapshot.build_strategy_prerequisite_recovery_ledger(
            {
                "quant_packet": {
                    "status": "ready",
                    "data_status": "ready",
                    "score": 68,
                    "summary": "量化推演已回流。",
                    "updated_at": "2026-06-04T10:00:00",
                    "source": "本地量化缓存",
                },
                "discipline_packet": {
                    "status": "failed",
                    "data_status": "permission_denied",
                    "backtest_status": "回测缓存不可用",
                    "source": "本地回测缓存",
                },
            }
        )
        by_key = {item["key"]: item for item in ledger["items"]}

        self.assertEqual(ledger["title"], "策略前置能力回流总账")
        self.assertEqual(ledger["status"], "blocked")
        self.assertEqual(ledger["recovered_count"], 1)
        self.assertEqual(ledger["blocked_count"], 1)
        self.assertIn("已回流 1", ledger["summary"])
        self.assertIn("仍受限 1", ledger["summary"])
        self.assertEqual(by_key["quant_projection"]["ledger_label"], "已回流")
        self.assertIn("辅助评分", by_key["quant_projection"]["decision_impact"])
        self.assertEqual(by_key["quant_projection"]["writes_packet"], "command_center_quant_packet")
        self.assertIn("量化推演", by_key["quant_projection"]["toolbox_entry"])
        self.assertIn("不能把策略建议当成已验证执行方案", by_key["discipline_backtest"]["decision_impact"])
        self.assertEqual(by_key["discipline_backtest"]["refresh_policy"], "button_gated")
        self.assertFalse(ledger["deepseek_called"])
        self.assertEqual(ledger["external_call_policy"], "not_triggered")
        self.assertIn("不会自动运行回测", ledger["safe_mode_text"])
        json.dumps(ledger, ensure_ascii=False)

    def test_legacy_a_share_gap_summary_focuses_limit_and_chip(self):
        summary = snapshot.build_legacy_a_share_gap_summary(
            {
                "limit_emotion_packet": {
                    "status": "failed",
                    "capability_state": "permission_denied",
                    "recovery_state": "blocked",
                    "status_label": "权限不足",
                    "source": "Tushare limit_cpt_list",
                },
                "chip_packet": {
                    "status": "waiting",
                    "capability_state": "empty_recent",
                    "recovery_state": "waiting",
                    "status_label": "近期无数据",
                    "source": "Tushare cyq_perf/cyq_chips",
                },
                "moneyflow_packet": {
                    "status": "ready",
                    "data_status": "ready",
                    "recovery_state": "recovered",
                    "status_label": "可用",
                },
            }
        )
        dumped = json.dumps(summary, ensure_ascii=False)

        self.assertEqual(summary["title"], "旧能力缺口：涨跌停/情绪 · 筹码/胜率")
        self.assertEqual(summary["tone"], "failed")
        self.assertEqual(summary["summary"], "已回流 0｜仍受限 1｜待验证 1")
        self.assertEqual([item["key"] for item in summary["items"]], ["limit_emotion", "chip_radar"])
        self.assertIn("不能把缺失数据当成无风险", dumped)
        self.assertIn("页面打开不会自动请求 Tushare", dumped)
        self.assertIn("Tushare 之前拉满不等于今天一定可见", dumped)
        self.assertIn("limit_cpt_list 权限不足", dumped)
        self.assertIn("cyq_perf 或 cyq_chips 权限", dumped)
        self.assertIn("近期无数据或缓存过期", dumped)
        self.assertIn("只检测 stk_limit / limit_list_d / limit_cpt_list", dumped)
        self.assertIn("只检测 cyq_perf / cyq_chips", dumped)
        self.assertIn("缺少筹码/胜率", dumped)
        self.assertIn("command_center_limit_emotion_packet", dumped)
        self.assertIn("command_center_chip_packet", dumped)
        for item in summary["items"]:
            self.assertTrue(item["manual_recovery_steps"])
            self.assertIn("why_not_found", item)
            self.assertIn("button_context", item)
            self.assertIn("decision_guardrail", item)
            self.assertFalse(item["deepseek_called"])
        self.assertFalse(summary["deepseek_called"])

    def test_home_snapshot_includes_a_share_fact_recovery_summary(self):
        today = _dt.date.today().isoformat()
        payload = snapshot.build_home_action_snapshot(
            {
                "command_center_decision_packet": {
                    "status": "ready",
                    "overall_action": "等待",
                    "updated_at": f"{today}T10:00:00",
                },
                "command_center_moneyflow_packet": {
                    "status": "ready",
                    "data_status": "ready",
                    "recovery_state": "recovered",
                    "status_label": "可用",
                    "updated_at": f"{today}T10:01:00",
                },
                "command_center_margin_packet": {
                    "status": "failed",
                    "capability_state": "permission_denied",
                    "recovery_state": "blocked",
                    "status_label": "权限不足",
                    "updated_at": f"{today}T10:01:00",
                },
            },
            target="002008.SZ",
            now=f"{today}T10:02:00",
        )

        summary = payload["a_share_fact_recovery_summary"]
        self.assertEqual(summary["recovered_count"], 1)
        self.assertEqual(summary["blocked_count"], 1)
        self.assertIn("A股事实 5 项", summary["summary"])
        dumped = json.dumps(summary, ensure_ascii=False)
        self.assertIn("个股资金流", dumped)
        self.assertIn("融资融券", dumped)
        self.assertIn("command_center_margin_packet", dumped)
        self.assertIn("点击“手动检测融资融券”", dumped)
        self.assertFalse(summary["deepseek_called"])
        legacy_gap = payload["legacy_a_share_gap_summary"]
        self.assertIn("涨跌停/情绪", json.dumps(legacy_gap, ensure_ascii=False))
        self.assertIn("筹码/胜率", json.dumps(legacy_gap, ensure_ascii=False))
        self.assertFalse(legacy_gap["deepseek_called"])
        ledger = payload["a_share_evidence_recovery_ledger"]
        self.assertEqual(ledger["title"], "A股证据回流总账")
        self.assertIn("融资融券", json.dumps(ledger, ensure_ascii=False))
        self.assertIn("阻断加仓", json.dumps(ledger, ensure_ascii=False))
        self.assertFalse(ledger["deepseek_called"])
        strategy_ledger = payload["strategy_prerequisite_recovery_ledger"]
        strategy_dumped = json.dumps(strategy_ledger, ensure_ascii=False)
        self.assertEqual(strategy_ledger["title"], "策略前置能力回流总账")
        self.assertIn("量化推演", strategy_dumped)
        self.assertIn("交易纪律/回测", strategy_dumped)
        self.assertIn("不会自动运行回测", strategy_ledger["safe_mode_text"])
        self.assertFalse(strategy_ledger["deepseek_called"])

    def test_home_snapshot_persists_hard_risk_packet(self):
        today = _dt.date.today().isoformat()
        state = {
            "command_center_decision_packet": {
                "status": "ready",
                "overall_action": "等待",
                "updated_at": f"{today}T10:00:00",
            },
            "a_share_professional_facts": {
                "verified_hard_risks": {
                    "available": True,
                    "target": "002008.SZ",
                    "updated_at": f"{today}T10:01:00",
                    "risk_items": [
                        {
                            "type": "公告风险",
                            "message": "减持计划待验证",
                            "date": "20260603",
                            "source": "Tushare anns_d",
                        }
                    ],
                }
            },
        }

        payload = snapshot.build_home_action_snapshot(state, target="002008.SZ", now=f"{today}T10:02:00")

        self.assertEqual(payload["hard_risk_packet"]["data_status"], "ready")
        self.assertEqual(payload["hard_risk_packet"]["risk_state"], "风险线索存在")
        self.assertEqual(payload["hard_risk_packet"]["risk_item_count"], 1)
        self.assertIn("减持计划待验证", payload["hard_risk_packet"]["risk_items"][0]["message"])
        diagnostic_dump = json.dumps(payload["a_share_user_data_diagnostic"], ensure_ascii=False)
        self.assertIn("公告 / 硬风险", diagnostic_dump)
        hard_item = next(item for item in payload["a_share_user_data_diagnostic"]["items"] if item["key"] == "hard_risk")
        self.assertEqual(hard_item["status"], "available")
        self.assertEqual(hard_item["writes_packet"], "command_center_hard_risk_packet")
        self.assertNotIn("command_center_hard_risk_packet", json.dumps(payload["a_share_user_data_diagnostic"]["recovery_actions"], ensure_ascii=False))
        self.assertFalse(payload["hard_risk_packet"]["deepseek_called"])

    def test_home_snapshot_reads_legacy_tianyan_hard_risk_packet(self):
        today = _dt.date.today().isoformat()
        state = {
            "command_center_decision_packet": {
                "status": "ready",
                "overall_action": "等待",
                "updated_at": f"{today}T10:00:00",
            },
            "tianyan_risk_fact_packet": {
                "verified_hard_risks": {
                    "available": True,
                    "updated_at": f"{today}T10:01:00",
                    "announcements": {
                        "available": True,
                        "source": "Tushare",
                        "api": "anns_d",
                        "rows": [
                            {"ann_date": "20260603", "title": "关于风险提示的公告"}
                        ],
                        "risk_flags": ["公告标题线索涉及：风险提示"],
                    },
                }
            },
        }

        payload = snapshot.build_home_action_snapshot(state, target="002008.SZ", now=f"{today}T10:02:00")

        self.assertEqual(payload["hard_risk_packet"]["source_key"], "tianyan_risk_fact_packet.verified_hard_risks")
        self.assertEqual(payload["hard_risk_packet"]["data_status"], "ready")
        self.assertIn("风险提示", json.dumps(payload["hard_risk_packet"], ensure_ascii=False))
        self.assertFalse(payload["hard_risk_packet"]["deepseek_called"])

    def test_home_snapshot_persists_margin_packet(self):
        today = _dt.date.today().isoformat()
        state = {
            "command_center_decision_packet": {
                "status": "ready",
                "overall_action": "等待",
                "updated_at": f"{today}T10:00:00",
            },
            "a_share_professional_facts": {
                "margin": {
                    "available": True,
                    "date": "20260603",
                    "financing_balance_yi": 12.3,
                    "financing_buy_yi": 1.2,
                    "margin_balance_yi": 13.5,
                    "updated_at": f"{today}T10:01:00",
                },
            },
        }

        payload = snapshot.build_home_action_snapshot(state, target="002008.SZ", now=f"{today}T10:02:00")

        self.assertEqual(payload["margin_packet"]["data_status"], "ready")
        self.assertEqual(payload["margin_packet"]["leverage_state"], "融资买入增加")
        self.assertEqual(payload["margin_packet"]["financing_balance_yi"], 12.3)
        self.assertFalse(payload["margin_packet"]["deepseek_called"])

    def test_home_snapshot_persists_limit_emotion_packet(self):
        today = _dt.date.today().isoformat()
        state = {
            "command_center_decision_packet": {
                "status": "ready",
                "overall_action": "等待",
                "updated_at": f"{today}T10:00:00",
            },
            "a_share_professional_facts": {
                "limit_emotion": {
                    "available": True,
                    "boundary_available": True,
                    "records_available": True,
                    "latest_date": "20260603",
                    "up_limit": 12.34,
                    "down_limit": 10.10,
                    "distance_to_up_pct": 2.1,
                    "limit_records": [{"日期": "2026-06-03", "类型": "涨停", "连板统计": "2连"}],
                    "updated_at": f"{today}T10:01:00",
                },
            },
        }

        payload = snapshot.build_home_action_snapshot(state, target="002008.SZ", now=f"{today}T10:02:00")

        self.assertEqual(payload["limit_emotion_packet"]["data_status"], "ready")
        self.assertEqual(payload["limit_emotion_packet"]["emotion_state"], "接近涨停/追高区")
        self.assertEqual(payload["limit_emotion_packet"]["up_limit"], 12.34)
        self.assertFalse(payload["limit_emotion_packet"]["deepseek_called"])

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
