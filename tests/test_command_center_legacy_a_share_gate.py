import ast
import copy
import json
import unittest
from pathlib import Path

import command_center_legacy_a_share_gate as gate
import command_center_home_snapshot as home_snapshot
import market_data_capability as capability


class CommandCenterLegacyAShareGateTests(unittest.TestCase):
    def test_missing_facts_do_not_count_as_cache(self):
        self.assertFalse(gate.has_a_share_professional_cache(None))
        self.assertFalse(gate.has_a_share_professional_cache({}))

    def test_manual_gate_packet_does_not_count_as_cache(self):
        packet = gate.build_manual_gate_a_share_professional_facts(
            "002008",
            updated_at="2026-06-03T10:00:00",
        )

        self.assertFalse(gate.has_a_share_professional_cache(packet))
        self.assertFalse(packet["available"])
        self.assertFalse(packet["deepseek_called"])
        self.assertIn("自动检测中", packet["missing_items"][0])
        self.assertIn("TTL", packet["missing_items"][0])
        json.dumps(packet, ensure_ascii=False)

    def test_manual_gate_user_text_is_auto_hydrated(self):
        self.assertIn("自动请求必要 Tushare", gate.refresh_caption())
        self.assertIn("强制刷新", gate.refresh_caption())
        self.assertIn("自动检测必要 Tushare", gate.empty_notice())
        self.assertNotIn("重新请求当前可用最新数据", gate.refresh_caption())

    def test_existing_updated_fact_counts_as_cache_even_if_unavailable(self):
        self.assertTrue(
            gate.has_a_share_professional_cache(
                {
                    "dragon_tiger": {
                        "available": False,
                        "message": "近30日未见龙虎榜上榜记录",
                        "updated_at": "2026-06-03T10:00:00",
                    }
                }
            )
        )

    def test_manual_gate_capability_items_require_manual_refresh(self):
        packet = gate.build_manual_gate_a_share_professional_facts(
            "002008",
            updated_at="2026-06-03T10:00:00",
        )
        by_section = {item["section"]: item for item in packet["data_capability"]["items"]}

        for section in gate.SECTION_SPECS:
            self.assertEqual(by_section[section]["capability_state"], capability.STATE_REQUIRES_MANUAL_REFRESH)
            self.assertEqual(by_section[section]["status"], "需要手动刷新")
            self.assertFalse(by_section[section]["ok"])

    def test_status_strip_summarizes_manual_gate_without_debug_text(self):
        packet = gate.build_manual_gate_a_share_professional_facts(
            "002008",
            updated_at="2026-06-03T10:00:00",
        )
        strip = gate.build_a_share_status_strip(packet, packet["data_capability"])
        dumped = json.dumps(strip, ensure_ascii=False)

        self.assertEqual(strip["status_label"], "自动检测中")
        self.assertIn("自动检测中", strip["summary"])
        self.assertFalse(strip["deepseek_called"])
        self.assertNotIn("commit", dumped.lower())
        self.assertNotIn("feature present", dumped)

    def test_status_strip_prioritizes_restricted_capability(self):
        packet = {
            "updated_at": "2026-06-03T10:00:00",
            "margin": {"available": False, "updated_at": "2026-06-03T10:00:00"},
            "data_capability": {
                "source": "Tushare A股专业事实",
                "items": [
                    {"section": "moneyflow", "label": "个股资金流", "capability_state": capability.STATE_AVAILABLE, "status": "可用"},
                    {"section": "margin", "label": "融资融券", "capability_state": capability.STATE_PERMISSION_DENIED, "status": "权限不足"},
                ],
            },
        }

        strip = gate.build_a_share_status_strip(packet)

        self.assertEqual(strip["status_label"], "部分接口受限")
        self.assertEqual(strip["tone"], "failed")
        self.assertIn("可用 1", strip["summary"])
        self.assertIn("受限/失败 1", strip["summary"])

    def test_completion_notice_does_not_call_restricted_data_complete(self):
        strip = {
            "status_label": "部分接口受限",
            "tone": "failed",
            "summary": "可用 1｜受限/失败 2｜待验证 1｜手动刷新 1",
        }

        notice = gate.build_a_share_status_completion_notice(strip)

        self.assertTrue(notice["label"].startswith("部分受限："))
        self.assertNotIn("完成：", notice["label"])
        self.assertIn("不能把缺失数据当成无风险", notice["decision_guardrail"])
        self.assertIn("不代表所有 Tushare 专业接口均可用", notice["manual_note"])
        self.assertFalse(notice["deepseek_called"])
        json.dumps(notice, ensure_ascii=False)

    def test_completion_notice_separates_manual_gate_from_success(self):
        strip = {
            "status_label": "自动检测中",
            "tone": "missing",
            "summary": "暂无 A股专业事实缓存；当前页按 TTL 自动请求必要 Tushare 专业接口。",
        }

        notice = gate.build_a_share_status_completion_notice(strip)

        self.assertTrue(notice["label"].startswith("自动检测中："))
        self.assertNotIn("完成：", notice["label"])
        self.assertIn("自动检测未取得可用结果", notice["decision_guardrail"])
        self.assertFalse(notice["deepseek_called"])

    def test_packet_summary_counts_ready_cached_waiting_and_failed(self):
        summary = gate.build_legacy_a_share_packet_summary(
            dragon_tiger_packet={
                "status": "ready",
                "data_status": "ready",
                "source": "Tushare 龙虎榜缓存",
                "api": "top_list/top_inst",
                "updated_at": "2026-06-03T10:00:00",
                "summary": "龙虎榜状态：席位净买入。",
            },
            margin_packet={
                "status": "failed",
                "data_status": "missing",
                "source": "Tushare margin_detail 缓存",
                "error": "权限不足",
            },
            moneyflow_packet={
                "status": "partial",
                "data_status": "cached",
                "summary": "近5日未取得可验证资金流。",
            },
            limit_emotion_packet={"status": "waiting"},
            chip_packet={},
        )

        self.assertEqual(summary["status_label"], "部分接口受限")
        self.assertEqual(summary["counts"], {"ready": 1, "cached": 1, "waiting": 2, "failed": 1})
        self.assertIn("已回流 1", summary["summary"])
        self.assertIn("按 TTL 自动检测", summary["manual_note"])
        self.assertFalse(summary["deepseek_called"])
        by_key = {item["key"]: item for item in summary["items"]}
        self.assertEqual(by_key["dragon_tiger"]["status"], "已回流")
        self.assertEqual(by_key["margin"]["status"], "受限/失败")
        self.assertEqual(by_key["moneyflow"]["status"], "使用缓存/待复核")
        self.assertEqual(by_key["chip_radar"]["status"], "自动检测中")

    def test_packet_summary_is_json_friendly_and_does_not_mutate_input(self):
        packet = {
            "status": "ready",
            "data_status": "ready",
            "risk_notes": ["资金净流入只作验证线索"],
            "updated_at": "2026-06-03T10:00:00",
        }
        before = copy.deepcopy(packet)

        summary = gate.build_legacy_a_share_packet_summary(moneyflow_packet=packet)

        self.assertEqual(packet, before)
        json.dumps(summary, ensure_ascii=False)
        moneyflow_item = [item for item in summary["items"] if item["key"] == "moneyflow"][0]
        self.assertEqual(moneyflow_item["risk_note"], "资金净流入只作验证线索")
        self.assertFalse(any(item["deepseek_called"] for item in summary["items"]))

    def test_packet_summary_handles_empty_packets(self):
        summary = gate.build_legacy_a_share_packet_summary()

        self.assertEqual(summary["status_label"], "自动检测中")
        self.assertEqual(len(summary["items"]), 5)
        self.assertEqual(summary["counts"]["waiting"], 5)
        self.assertTrue(all(item["status"] == "自动检测中" for item in summary["items"]))
        json.dumps(summary, ensure_ascii=False)

    def test_primary_fact_cards_render_ready_packet_fields(self):
        cards = gate.build_legacy_a_share_primary_fact_cards(
            dragon_tiger_packet={
                "status": "ready",
                "data_status": "ready",
                "trade_date": "2026-06-03",
                "close": 12.34,
                "pct_change": 3.21,
                "buy_amount_yi": 1.2,
                "sell_amount_yi": 0.4,
                "net_buy_amount_yi": 0.8,
                "reason": "日涨幅偏离值达7%",
                "activity_state": "席位净买入",
                "source": "Tushare 龙虎榜缓存",
                "api": "top_list/top_inst",
                "updated_at": "2026-06-03T20:00:00",
            },
            margin_packet={
                "status": "ready",
                "financing_balance_yi": 10.1,
                "financing_buy_yi": 0.5,
                "margin_balance_yi": 11.2,
                "leverage_state": "杠杆余额可参考",
            },
            moneyflow_packet={
                "status": "ready",
                "main_net_yi": 0.3,
                "large_net_yi": -0.1,
                "medium_net_yi": 0.2,
                "small_net_yi": -0.4,
                "five_day_main_net_yi": 1.1,
                "flow_state": "主力净流入",
            },
        )

        self.assertEqual(cards["title"], "A股专业主事实")
        self.assertFalse(cards["deepseek_called"])
        self.assertEqual(len(cards["cards"]), 3)
        dragon_card = cards["cards"][0]
        self.assertEqual(dragon_card["status"], "已回流")
        self.assertIn("¥12.34", dragon_card["metrics"][1]["value"])
        self.assertIn("+3.21%", dragon_card["metrics"][1]["value"])
        self.assertIn("+0.80亿", dragon_card["metrics"][2]["value"])
        self.assertIn("上榜原因", " ".join(dragon_card["captions"]))
        self.assertIn("Tushare 龙虎榜缓存", dragon_card["source_caption"])
        self.assertEqual(dragon_card["recovery_action"]["refresh_policy"], "not_needed")
        self.assertEqual(dragon_card["recovery_action"]["writes_packet"], "command_center_dragon_tiger_packet")
        json.dumps(cards, ensure_ascii=False)

    def test_primary_fact_cards_hide_metrics_when_waiting_or_failed(self):
        cards = gate.build_legacy_a_share_primary_fact_cards(
            dragon_tiger_packet={"status": "waiting", "summary": "龙虎榜待刷新"},
            margin_packet={"status": "failed", "error": "权限不足"},
            moneyflow_packet={},
        )
        by_key = {card["key"]: card for card in cards["cards"]}

        self.assertEqual(by_key["dragon_tiger"]["status"], "自动检测中")
        self.assertEqual(by_key["margin"]["status"], "受限/失败")
        self.assertEqual(by_key["moneyflow"]["status"], "自动检测中")
        self.assertEqual(by_key["dragon_tiger"]["metrics"], [])
        self.assertEqual(by_key["margin"]["metrics"], [])
        self.assertIn("权限不足", by_key["margin"]["risk_note"])
        self.assertEqual(by_key["dragon_tiger"]["recovery_action"]["refresh_policy"], "button_gated")
        self.assertEqual(by_key["dragon_tiger"]["recovery_action"]["writes_packet"], "command_center_dragon_tiger_packet")
        self.assertIn("强制刷新龙虎榜", by_key["dragon_tiger"]["recovery_action"]["action_label"])
        self.assertEqual(by_key["dragon_tiger"]["recovery_action"]["legacy_tab"], "下一票雷达")
        self.assertEqual(by_key["dragon_tiger"]["recovery_action"]["workspace_target"], "高级工具箱（旧版保留）")
        self.assertEqual(by_key["margin"]["recovery_action"]["writes_packet"], "command_center_margin_packet")
        self.assertIn("command_center_margin_packet", by_key["margin"]["packet_route_summary"])
        self.assertIn("今日总决策依据链", by_key["margin"]["packet_route_summary"])
        self.assertIn("不能支撑加仓", by_key["margin"]["decision_chain_effect"])
        self.assertIn("加融资", by_key["margin"]["decision_chain_effect"])
        self.assertFalse(by_key["margin"]["recovery_action"]["deepseek_called"])
        navigation_state = home_snapshot.build_tool_recovery_navigation_state(by_key["margin"]["recovery_action"])
        self.assertEqual(navigation_state["workspace_mode_v2"], "高级工具箱（旧版保留）")
        self.assertEqual(navigation_state["legacy_workspace_selected_tab"], "融资 ETF")
        self.assertEqual(navigation_state["command_center_last_tool_recovery_policy"], "navigation_only")
        self.assertEqual(navigation_state["command_center_last_tool_recovery_writes_packet"], "command_center_margin_packet")
        json.dumps(cards, ensure_ascii=False)

    def test_primary_fact_cards_do_not_mutate_input(self):
        packet = {
            "status": "ready",
            "main_net_yi": 1.0,
            "risk_notes": ["资金净流入只作验证线索"],
        }
        before = copy.deepcopy(packet)

        cards = gate.build_legacy_a_share_primary_fact_cards(moneyflow_packet=packet)

        self.assertEqual(packet, before)
        moneyflow_card = [card for card in cards["cards"] if card["key"] == "moneyflow"][0]
        self.assertEqual(moneyflow_card["risk_note"], "资金净流入只作验证线索")

    def test_secondary_fact_sections_render_limit_and_chip_packets(self):
        sections = gate.build_legacy_a_share_secondary_fact_sections(
            limit_emotion_packet={
                "status": "ready",
                "trade_date": "2026-06-03",
                "up_limit": 13.5,
                "down_limit": 11.05,
                "distance_to_up_pct": 2.1,
                "distance_to_down_pct": -7.8,
                "emotion_state": "情绪线索可参考",
                "limit_records": [{"date": "2026-06-02", "type": "涨停"}],
                "concept_top5": [{"name": "半导体", "limit_up_count": 8}],
                "source": "Tushare 涨跌停/情绪缓存",
            },
            chip_packet={
                "status": "ready",
                "trade_date": "2026-06-03",
                "winner_rate": 63.2,
                "weight_avg": 12.1,
                "current_vs_weight_avg_pct": 4.5,
                "cost_5pct": 9.8,
                "cost_50pct": 11.7,
                "cost_95pct": 15.2,
                "chip_pressure_comment": "筹码相对收敛",
                "chip_structure_comment": "筹码结构待复核",
                "chips_top_areas": [{"price": 12.0, "percent": 18.5}],
            },
        )

        self.assertEqual(sections["title"], "A股情绪与筹码事实")
        self.assertFalse(sections["deepseek_called"])
        self.assertEqual(len(sections["sections"]), 2)
        limit_section = sections["sections"][0]
        chip_section = sections["sections"][1]
        self.assertEqual(limit_section["status"], "已回流")
        self.assertIn("¥13.50", limit_section["metrics"][0]["value"])
        self.assertEqual(limit_section["tables"][0]["rows"][0]["type"], "涨停")
        self.assertEqual(limit_section["tables"][1]["rows"][0]["name"], "半导体")
        self.assertEqual(limit_section["recovery_action"]["refresh_policy"], "not_needed")
        self.assertEqual(limit_section["recovery_action"]["writes_packet"], "command_center_limit_emotion_packet")
        self.assertEqual(chip_section["status"], "已回流")
        self.assertIn("63.20%", chip_section["metrics"][1]["value"])
        self.assertIn("筹码成本", chip_section["captions"][0])
        self.assertIn("筹码密集区", " ".join(chip_section["captions"]))
        self.assertEqual(chip_section["recovery_action"]["writes_packet"], "command_center_chip_packet")
        json.dumps(sections, ensure_ascii=False)

    def test_secondary_fact_sections_hide_metrics_when_waiting_or_failed(self):
        sections = gate.build_legacy_a_share_secondary_fact_sections(
            limit_emotion_packet={"status": "waiting", "summary": "涨跌停待刷新"},
            chip_packet={"status": "failed", "error": "权限不足"},
        )
        by_key = {section["key"]: section for section in sections["sections"]}

        self.assertEqual(by_key["limit_emotion"]["status"], "自动检测中")
        self.assertEqual(by_key["chip_radar"]["status"], "受限/失败")
        self.assertEqual(by_key["limit_emotion"]["metrics"], [])
        self.assertEqual(by_key["chip_radar"]["metrics"], [])
        self.assertIn("权限不足", by_key["chip_radar"]["risk_note"])
        self.assertEqual(by_key["limit_emotion"]["recovery_action"]["refresh_policy"], "button_gated")
        self.assertEqual(by_key["limit_emotion"]["recovery_action"]["writes_packet"], "command_center_limit_emotion_packet")
        self.assertEqual(by_key["limit_emotion"]["recovery_action"]["legacy_tab"], "数据源体检")
        self.assertIn("command_center_limit_emotion_packet", by_key["limit_emotion"]["packet_route_summary"])
        self.assertIn("待验证", by_key["limit_emotion"]["decision_chain_effect"])
        self.assertEqual(by_key["chip_radar"]["recovery_action"]["writes_packet"], "command_center_chip_packet")
        self.assertEqual(by_key["chip_radar"]["recovery_action"]["legacy_tab"], "量化推演")
        self.assertIn("command_center_chip_packet", by_key["chip_radar"]["packet_route_summary"])
        self.assertIn("不能支撑加仓", by_key["chip_radar"]["decision_chain_effect"])
        self.assertFalse(by_key["chip_radar"]["recovery_action"]["deepseek_called"])
        navigation_state = home_snapshot.build_tool_recovery_navigation_state(by_key["chip_radar"]["recovery_action"])
        self.assertEqual(navigation_state["legacy_workspace_selected_tab"], "量化推演")
        self.assertEqual(navigation_state["command_center_last_tool_recovery_writes_packet"], "command_center_chip_packet")
        json.dumps(sections, ensure_ascii=False)

    def test_secondary_fact_sections_do_not_mutate_input(self):
        packet = {
            "status": "ready",
            "limit_records": [{"date": "2026-06-03", "type": "炸板"}],
            "risk_notes": ["炸板记录只是事件证据"],
        }
        before = copy.deepcopy(packet)

        sections = gate.build_legacy_a_share_secondary_fact_sections(limit_emotion_packet=packet)

        self.assertEqual(packet, before)
        limit_section = [section for section in sections["sections"] if section["key"] == "limit_emotion"][0]
        self.assertEqual(limit_section["risk_note"], "炸板记录只是事件证据")

    def test_war_room_inputs_prefer_command_center_packets(self):
        inputs = gate.build_legacy_a_share_war_room_inputs(
            chip_packet={"weight_avg": 12.3},
            limit_emotion_packet={"up_limit": 13.5, "down_limit": 11.05},
            moneyflow_packet={"main_net_yi": 0.6, "five_day_main_net_yi": -1.2},
            technical_facts={"ma20": 12.0, "ma60": 10.5},
            position_profile={
                "normalized_position_state": "已持仓",
                "cost_price": 9.9,
                "holding_units": 1000,
                "allow_pnl": True,
            },
        )

        self.assertEqual(inputs["chip_center"], 12.3)
        self.assertEqual(inputs["limit_up"], 13.5)
        self.assertEqual(inputs["limit_down"], 11.05)
        self.assertEqual(inputs["today_main_net_yi"], 0.6)
        self.assertEqual(inputs["five_day_main_net_yi"], -1.2)
        self.assertEqual(inputs["ma20"], 12.0)
        self.assertEqual(inputs["ma60"], 10.5)
        self.assertTrue(inputs["is_holding"])
        self.assertEqual(inputs["cost_price"], 9.9)
        self.assertEqual(inputs["shares"], 1000)
        self.assertEqual(inputs["source_fields"]["chip_center"], "command_center_chip_packet.weight_avg")
        self.assertFalse(inputs["deepseek_called"])
        json.dumps(inputs, ensure_ascii=False)

    def test_war_room_inputs_fallback_to_technical_snapshot_and_do_not_mutate(self):
        chip_packet = {"weight_avg": "12.3"}
        technical_snapshot = {"ma20": "11.1", "ma60": "9.8"}
        profile = {"normalized_position_state": "未买入，纯观察", "cost_price": 8.8, "allow_pnl": False}
        before = copy.deepcopy({"chip": chip_packet, "snapshot": technical_snapshot, "profile": profile})

        inputs = gate.build_legacy_a_share_war_room_inputs(
            chip_packet=chip_packet,
            technical_facts={},
            technical_snapshot=technical_snapshot,
            position_profile=profile,
            position_status="已持仓",
        )

        self.assertEqual({"chip": chip_packet, "snapshot": technical_snapshot, "profile": profile}, before)
        self.assertEqual(inputs["chip_center"], 12.3)
        self.assertEqual(inputs["ma20"], 11.1)
        self.assertEqual(inputs["ma60"], 9.8)
        self.assertFalse(inputs["is_holding"])
        self.assertIsNone(inputs["shares"])
        json.dumps(inputs, ensure_ascii=False)

    def test_prompt_fact_payloads_convert_ready_packets_to_legacy_shape(self):
        payloads = gate.build_legacy_a_share_prompt_fact_payloads(
            dragon_tiger_packet={
                "status": "ready",
                "trade_date": "2026-06-03",
                "reason": "日涨幅偏离值达7%",
                "net_buy_amount_yi": 0.8,
                "inst_summary": "机构净买入",
            },
            margin_packet={
                "status": "ready",
                "trade_date": "2026-06-03",
                "financing_balance_yi": 10.1,
                "financing_buy_yi": 0.5,
            },
            moneyflow_packet={
                "status": "ready",
                "trade_date": "2026-06-03",
                "main_net_yi": 0.6,
                "large_net_yi": -0.1,
                "medium_net_yi": 0.2,
                "small_net_yi": -0.3,
                "five_day_main_net_yi": 1.2,
                "flow_state": "主力净流入",
                "summary": "资金流状态：主力净流入。",
            },
            limit_emotion_packet={
                "status": "ready",
                "trade_date": "2026-06-03",
                "up_limit": 13.5,
                "down_limit": 11.05,
                "distance_to_up_pct": 2.1,
                "limit_records": [{"date": "2026-06-02", "type": "涨停"}],
                "concept_top5": [{"name": "半导体"}],
            },
            chip_packet={
                "status": "ready",
                "trade_date": "2026-06-03",
                "winner_rate": 63.2,
                "weight_avg": 12.1,
                "cost_5pct": 9.8,
                "cost_50pct": 11.7,
                "cost_95pct": 15.2,
                "chip_pressure_comment": "筹码相对收敛",
            },
        )

        self.assertTrue(payloads["dragon_tiger"]["available"])
        self.assertEqual(payloads["dragon_tiger"]["latest_date"], "2026-06-03")
        self.assertTrue(payloads["margin"]["available"])
        self.assertEqual(payloads["moneyflow"]["main_net_yi"], 0.6)
        self.assertEqual(payloads["moneyflow"]["direction"], "主力净流入")
        self.assertTrue(payloads["limit_emotion"]["boundary_available"])
        self.assertTrue(payloads["limit_emotion"]["records_available"])
        self.assertEqual(payloads["limit_emotion"]["limit_records"][0]["type"], "涨停")
        self.assertTrue(payloads["chip_radar"]["available"])
        self.assertEqual(payloads["chip_radar"]["weight_avg"], 12.1)
        self.assertEqual(payloads["source"], "command_center_*_packet")
        self.assertFalse(payloads["deepseek_called"])
        json.dumps(payloads, ensure_ascii=False)

    def test_prompt_fact_payloads_do_not_mark_missing_packets_available_or_mutate(self):
        moneyflow_packet = {"status": "waiting", "summary": "个股资金流待刷新"}
        chip_packet = {"status": "failed", "error": "权限不足"}
        before = copy.deepcopy({"moneyflow": moneyflow_packet, "chip": chip_packet})

        payloads = gate.build_legacy_a_share_prompt_fact_payloads(
            moneyflow_packet=moneyflow_packet,
            chip_packet=chip_packet,
        )

        self.assertEqual({"moneyflow": moneyflow_packet, "chip": chip_packet}, before)
        self.assertFalse(payloads["moneyflow"]["available"])
        self.assertEqual(payloads["moneyflow"]["note"] if "note" in payloads["moneyflow"] else payloads["moneyflow"]["message"], "个股资金流待刷新")
        self.assertFalse(payloads["chip_radar"]["available"])
        self.assertEqual(payloads["chip_radar"]["chip_pressure_comment"], "暂无可验证数据")
        json.dumps(payloads, ensure_ascii=False)

    def test_prompt_fact_payloads_do_not_promote_cached_limit_boundaries(self):
        payloads = gate.build_legacy_a_share_prompt_fact_payloads(
            limit_emotion_packet={
                "status": "partial",
                "data_status": "cached",
                "boundary_available": True,
                "records_available": True,
                "up_limit": 13.5,
                "limit_records": [{"date": "2026-06-02", "type": "涨停"}],
                "summary": "使用缓存，待复核。",
            }
        )

        self.assertFalse(payloads["limit_emotion"]["available"])
        self.assertFalse(payloads["limit_emotion"]["boundary_available"])
        self.assertFalse(payloads["limit_emotion"]["records_available"])
        self.assertEqual(payloads["limit_emotion"]["up_limit"], "")
        self.assertEqual(payloads["limit_emotion"]["limit_records"], [])
        self.assertEqual(payloads["limit_emotion"]["message"], "使用缓存，待复核。")

    def test_forbidden_imports(self):
        tree = ast.parse(Path("command_center_legacy_a_share_gate.py").read_text(encoding="utf-8"))
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
