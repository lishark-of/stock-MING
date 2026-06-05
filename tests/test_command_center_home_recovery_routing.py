import ast
import unittest
from pathlib import Path


def _function_node(name):
    tree = ast.parse(Path("app.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"Function not found: {name}")


def _function_tokens(name):
    node = _function_node(name)
    values = set()
    for item in ast.walk(node):
        if isinstance(item, ast.Constant) and isinstance(item.value, str):
            values.add(item.value)
        elif isinstance(item, ast.Name):
            values.add(item.id)
        elif isinstance(item, ast.Attribute):
            values.add(item.attr)
    return values


def _assert_token_contains(testcase, tokens, fragment):
    testcase.assertTrue(
        any(fragment in token for token in tokens),
        f"Expected token containing {fragment!r}",
    )


class CommandCenterHomeRecoveryRoutingTests(unittest.TestCase):
    def test_home_diagnostic_recovery_routes_chip_and_hard_risk(self):
        tokens = _function_tokens("render_home_a_share_diagnostic_recovery_controls")

        _assert_token_contains(self, tokens, "数据恢复中心｜A股接口检测")
        self.assertIn("chip_radar", tokens)
        self.assertIn("hard_risk", tokens)
        self.assertIn("_run_manual_chip_radar_capability_check", tokens)
        self.assertIn("_run_manual_hard_risk_capability_check", tokens)
        self.assertIn("btn_cc_home_a_share_diagnostic_recovery_", tokens)

    def test_legacy_a_share_page_surfaces_gap_recovery_ledger(self):
        tokens = _function_tokens("render_legacy_a_share_gap_recovery_panel")
        source = Path("app.py").read_text(encoding="utf-8")

        _assert_token_contains(self, tokens, "数据恢复中心｜旧版数据缺口总账")
        _assert_token_contains(self, tokens, "为什么搜不到：")
        _assert_token_contains(self, tokens, "按钮说明：")
        _assert_token_contains(self, tokens, "决策保护：")
        _assert_token_contains(self, tokens, "打开恢复入口：")
        self.assertIn("build_legacy_a_share_gap_summary", tokens)
        self.assertIn("build_old_workspace_data_absence_ledger", tokens)
        self.assertIn("build_tool_recovery_navigation_state", tokens)
        self.assertIn("_apply_tool_recovery_navigation_state", tokens)
        self.assertIn("_apply_tool_recovery_navigation_state(item, persist_snapshot=True)", source)
        self.assertIn("render_legacy_a_share_gap_recovery_panel(legacy_gap_context", source)
        self.assertIn("command_center_limit_emotion_packet", source)
        self.assertIn("command_center_chip_packet", source)

    def test_tool_recovery_navigation_state_persists_latest_notice(self):
        tokens = _function_tokens("_apply_tool_recovery_navigation_state")

        self.assertIn("build_tool_recovery_navigation_state", tokens)
        self.assertIn("build_latest_recovery_result_notice", tokens)
        self.assertIn("latest_recovery_result_notice", tokens)
        self.assertIn("build_recovery_result_timeline", tokens)
        self.assertIn("command_center_recovery_result_timeline", tokens)
        self.assertIn("_persist_home_action_snapshot", tokens)

    def test_evidence_backfill_controls_are_labeled_as_recovery_center(self):
        tokens = _function_tokens("render_home_evidence_backfill_controls")

        _assert_token_contains(self, tokens, "数据恢复中心｜")
        _assert_token_contains(self, tokens, "数据恢复中心里的证据缺口")

    def test_a_share_capability_controls_include_hard_risk_check(self):
        tokens = _function_tokens("render_a_share_data_capability_controls")

        self.assertIn("hard_risk_capability_check", tokens)
        self.assertIn("检测公告硬风险", tokens)
        self.assertIn("_run_manual_hard_risk_capability_check", tokens)

    def test_home_snapshot_tool_navigation_uses_recovery_center_language(self):
        source = Path("visual_components.py").read_text(encoding="utf-8")

        self.assertIn("数据恢复中心｜手动恢复导航", source)
        self.assertIn("valid_recovery_navigation_actions", source)
        self.assertIn("data_recovery_center_actions[:6]", source)
        self.assertIn("恢复{_home_text(item.get('label'), '数据能力')}", source)

    def test_home_snapshot_shows_latest_recovery_result(self):
        source = Path("visual_components.py").read_text(encoding="utf-8")

        self.assertIn("latest_recovery_result_notice", source)
        self.assertIn("recovery_result_status_strip", source)
        self.assertIn("最近恢复结果", source)
        self.assertIn("最近恢复状态", source)
        self.assertIn("recovery_result_status_html", source)
        self.assertIn("使用缓存", source)
        self.assertIn("最近恢复影响", source)
        self.assertIn("latest_evidence_impact", source)
        self.assertIn("external_call_policy", source)
        self.assertIn("DeepSeek：未调用", source)
        self.assertIn("latest_recovery_context_html", source)
        self.assertIn("为什么搜不到：", source)
        self.assertIn("决策保护：", source)

    def test_manual_capability_buttons_record_latest_recovery_result(self):
        source = Path("app.py").read_text(encoding="utf-8")

        self.assertIn("_remember_a_share_manual_recovery_result", source)
        self.assertIn("command_center_last_a_share_diagnostic_recovery_result", source)
        self.assertIn("command_center_last_recovery_result_source", source)
        self.assertIn("command_center_limit_emotion_packet", source)
        self.assertIn("command_center_chip_packet", source)
        self.assertIn("btn_cc_home_evidence_backfill_", source)

    def test_legacy_tool_packet_writes_refresh_home_snapshot(self):
        source = Path("app.py").read_text(encoding="utf-8")
        tokens = _function_tokens("_remember_legacy_tool_packet_recovery_result")

        self.assertIn("_remember_legacy_tool_packet_recovery_result", source)
        self.assertIn("_persist_home_action_snapshot", tokens)
        self.assertIn("command_center_last_recovery_result_source", tokens)
        self.assertIn("tool_recovery", tokens)
        self.assertIn("command_center_discipline_packet", source)
        self.assertIn("command_center_quant_packet", source)
        self.assertIn("command_center_etf_packet", source)
        self.assertIn("command_center_radar_packet", source)
        self.assertIn("legacy_discipline", source)
        self.assertIn("legacy_quant", source)
        self.assertIn("legacy_margin_etf", source)
        self.assertIn("legacy_next_ticket_radar", source)

    def test_decision_and_strategy_cards_surface_projection_confidence(self):
        source = Path("visual_components.py").read_text(encoding="utf-8")

        self.assertIn("projection_confidence_summary", source)
        self.assertIn("路径：{escape(str(projection_confidence.get(\"label\") or \"路径待生成\"))}", source)
        self.assertIn("趋势推演门槛", source)
        self.assertIn("路径只做条件化推演，不直接决定仓位", source)
        self.assertIn("a_share_evidence_group_html", source)
        self.assertIn("A股证据分组：", source)
        self.assertIn("a_share_evidence_group_guidance", source)
        self.assertIn("a_share_evidence_module_panel", source)
        self.assertIn("A股证据模块恢复面板", source)
        self.assertIn("资金流、龙虎榜、融资融券、涨跌停和筹码", source)
        self.assertIn("evidence_module_dependencies", source)
        self.assertIn("A股证据模块：", source)
        self.assertIn("evidence_module_dependency_summary", source)
        self.assertIn("execution_guardrail_dependencies", source)
        self.assertIn("执行护栏：", source)
        self.assertIn("execution_guardrail_dependency_summary", source)
        self.assertIn("execution_guardrail_overview", source)
        self.assertIn("执行护栏总览", source)
        self.assertIn("A股证据条件门槛", source)
        self.assertIn("path_evidence_group_summary", source)
        self.assertIn("path_evidence_group_items", source)
        self.assertIn("core_evidence_action_brief", source)
        self.assertIn("A股核心证据执行摘要", source)
        self.assertIn("core_evidence_action_html", source)
        self.assertIn("tushare_gap_explainer", source)
        self.assertIn("Tushare 专业接口为什么搜不到", source)
        self.assertIn("决策保护：", source)
        self.assertIn("provider_gap_explainer", source)
        self.assertIn("多数据源为什么不可用", source)
        self.assertIn("discipline_decision_brief", source)
        self.assertIn("纪律/回测执行摘要", source)
        self.assertIn("quant_decision_brief", source)
        self.assertIn("量化推演执行摘要", source)

    def test_home_snapshot_renders_recovery_priority_lanes(self):
        source = Path("visual_components.py").read_text(encoding="utf-8")

        self.assertIn("priority_lanes", source)
        self.assertIn("recovery_priority_html", source)
        self.assertIn("recovery_priority_items", source)
        self.assertIn("恢复优先级影响", source)
        self.assertIn("legacy_migration_map", source)
        self.assertIn("旧版能力迁移地图", source)
        self.assertIn("old_workspace_capability_overview", source)
        self.assertIn("旧能力回流总览", source)
        self.assertIn("valid_legacy_migration_actions", source)
        self.assertIn("迁移地图｜打开旧工具", source)
        self.assertIn("completion_checks", source)
        self.assertIn("完成条件", source)
        self.assertIn("completion_progress", source)
        self.assertIn("迁移进度：", source)
        self.assertIn("目标 packet：", source)
        self.assertIn("待处理目标：", source)
        self.assertIn("build_legacy_migration_recovery_actions_snapshot", Path("command_center_home_snapshot.py").read_text(encoding="utf-8"))
        self.assertIn("legacy_migration_actions", Path("command_center_home_snapshot.py").read_text(encoding="utf-8"))
        self.assertIn("P0 权限/本会话跳过", Path("command_center_home_snapshot.py").read_text(encoding="utf-8"))
        self.assertIn("P1 缓存/近期无数据", Path("command_center_home_snapshot.py").read_text(encoding="utf-8"))
        self.assertIn("P2 旧工具 packet 迁移", Path("command_center_home_snapshot.py").read_text(encoding="utf-8"))

    def test_home_snapshot_renders_provider_diagnostic_cards(self):
        source = Path("visual_components.py").read_text(encoding="utf-8")

        self.assertIn("provider_diagnostic_cards", source)
        self.assertIn("provider_diagnostic_html", source)
        self.assertIn("provider_recovery_matrix", source)
        self.assertIn("数据源恢复矩阵", source)
        self.assertIn("诊断结论", source)
        self.assertIn("最近检查：", source)
        self.assertIn("失败/待处理：", source)
        self.assertIn("接口明细：", source)
        self.assertIn("interface_diagnostic_items", source)
        self.assertIn("interface_diagnostic_html", source)
        self.assertIn("接口诊断待生成", source)
        self.assertIn("接口原因", source)
        self.assertIn("按钮说明", source)
        self.assertIn("recovery_button_context", source)
        self.assertIn("为什么搜不到", source)
        self.assertIn("decision_priority_queue", source)
        self.assertIn("next_step_queue", source)
        self.assertIn("下一步恢复队列", source)
        self.assertIn("manual_only_text", source)
        self.assertIn("决策优先队列", source)
        self.assertIn("决策模式", source)
        self.assertIn("valid_decision_priority_actions", source)
        self.assertIn("btn_open_decision_priority_", source)
        self.assertIn("决策优先队列｜打开恢复入口", source)
        self.assertIn("recovery_result_status_label", source)
        self.assertIn("recovery_result_message", source)
        self.assertIn("恢复结果：", source)
        self.assertIn("recovery_result_overview", source)
        self.assertIn("恢复结果总览", source)
        self.assertIn("可进入决策链：", source)
        self.assertIn("result_groups", source)
        self.assertIn("recovery_result_group_html", source)
        self.assertIn("恢复分组", source)

    def test_home_snapshot_renders_data_health_ledger(self):
        source = Path("visual_components.py").read_text(encoding="utf-8")

        self.assertIn("data_health_ledger", source)
        self.assertIn("data_health_ledger_html", source)
        self.assertIn("接口级健康账本", source)
        self.assertIn("最近检查", source)
        self.assertIn("最近成功", source)

    def test_home_snapshot_surfaces_data_visibility_summary(self):
        source = Path("visual_components.py").read_text(encoding="utf-8")

        self.assertIn("build_data_health_visibility_summary", source)
        self.assertIn("data_health_visibility_html", source)
        self.assertIn("为什么搜不到", source)
        self.assertIn("root_cause_groups", source)
        self.assertIn("根因分组", source)
        self.assertIn("root_cause_label", source)
        self.assertIn("之前拉满为何不够", source)
        self.assertIn("why_previous_full_not_enough", source)
        self.assertIn("权限不足：", source)
        self.assertIn("本会话跳过：", source)
        self.assertIn("近期无数据：", source)
        self.assertIn("valid_data_health_visibility_actions", source)
        self.assertIn("btn_open_data_health_visibility_", source)
        self.assertIn("为什么搜不到｜打开恢复入口", source)
        snapshot_source = Path("command_center_home_snapshot.py").read_text(encoding="utf-8")
        self.assertIn("data_health_visibility", snapshot_source)
        self.assertIn("root_cause_source_label", snapshot_source)
        self.assertIn("root_cause_code", snapshot_source)
        self.assertIn("why_previous_full_not_enough", snapshot_source)
        self.assertIn("data_health_timeline_recovery_actions", source)
        self.assertIn("valid_data_health_timeline_actions", source)
        self.assertIn("btn_open_data_health_timeline_", source)
        self.assertIn("接口健康时间线｜最近失败/缓存恢复入口", source)

    def test_home_snapshot_renders_recovered_evidence_modules(self):
        source = Path("visual_components.py").read_text(encoding="utf-8")

        self.assertIn("recovered_evidence_modules", source)
        self.assertIn("已回流模块", source)
        self.assertIn("暂无已回流证据模块", source)
        self.assertIn("evidence_status_groups", source)
        self.assertIn("evidence_status_group_html", source)

    def test_home_snapshot_collapses_verbose_diagnostics(self):
        source = Path("visual_components.py").read_text(encoding="utf-8")

        self.assertIn('class="cc-home-details"', source)
        self.assertIn("_render_html(html)", source)
        self.assertIn("诊断详情：A股矩阵 / 数据能力控制台 / 原因解释", source)
        self.assertNotIn("旧工具恢复队列", source)
        self.assertNotIn("恢复动作：暂无需要手动恢复的数据源动作", source)

    def test_home_snapshot_renders_a_share_fact_recovery_summary(self):
        source = Path("visual_components.py").read_text(encoding="utf-8")

        self.assertIn("a_share_fact_recovery_summary", source)
        self.assertIn("A股事实回流", source)
        self.assertIn("A股事实 5 项：已回流 0｜仍受限 0｜待验证 5", source)
        self.assertIn("a_share_fact_summary_text", source)
        self.assertIn("A股事实：{escape(a_share_fact_summary_text)}", source)
        self.assertIn("legacy_a_share_gap_summary", source)
        self.assertIn("legacy_gap_html", source)
        self.assertIn("legacy_gap_item_html", source)
        self.assertIn("旧能力缺口待生成", source)
        self.assertIn("涨跌停/情绪、筹码/胜率", source)
        self.assertIn("为什么搜不到：", source)
        self.assertIn("按钮说明：", source)
        self.assertIn("决策保护：", source)
        self.assertIn("manual_recovery_steps", source)

    def test_refresh_summary_routes_a_share_fact_recovery_to_navigation_only(self):
        source = Path("app.py").read_text(encoding="utf-8")

        self.assertIn("A股事实回流状态", source)
        self.assertIn("进入恢复：{item.get('label') or 'A股事实'}", source)
        self.assertIn("_apply_tool_recovery_navigation_state(item)", source)
        self.assertIn("不会自动运行 Tushare、DeepSeek、回测或全市场扫描", source)

    def test_home_snapshot_renders_a_share_evidence_navigation_only_buttons(self):
        source = Path("visual_components.py").read_text(encoding="utf-8")

        self.assertIn("A股证据雷达｜打开恢复入口", source)
        self.assertIn("valid_evidence_navigation_actions", source)
        self.assertIn("btn_open_evidence_recovery_", source)
        self.assertIn("_apply_tool_recovery_navigation", source)
        self.assertIn("对应检测仍需在旧模块里手动点击", source)

    def test_margin_etf_refresh_writes_etf_and_margin_packets(self):
        tokens = _function_tokens("_cc_refresh_margin_etf_config")

        self.assertIn("command_center_etf_packet", tokens)
        self.assertIn("command_center_margin_packet", tokens)
        self.assertIn("sync_legacy_etf_packet", tokens)
        self.assertIn("build_command_center_margin_packet", tokens)
        _assert_token_contains(self, tokens, "融资 ETF 本地配置快照")

    def test_next_ticket_refresh_reads_legacy_radar_rows_and_writes_packet(self):
        tokens = _function_tokens("_cc_run_next_ticket_radar")

        self.assertIn("extract_legacy_radar_rows", tokens)
        self.assertIn("command_center_radar_packet", tokens)
        self.assertIn("sync_legacy_radar_packet", tokens)
        _assert_token_contains(self, tokens, "下一票雷达本地缓存快照")
        _assert_token_contains(self, tokens, "不触发全市场扫描")

    def test_legacy_a_share_screen_routes_diagnostic_to_recovery_controls(self):
        source = Path("app.py").read_text(encoding="utf-8")

        self.assertIn("render_home_a_share_diagnostic_recovery_controls(", source)
        self.assertIn('home_snapshot={"a_share_user_data_diagnostic": legacy_user_diagnostic}', source)
        self.assertIn('market_type="A股"', source)

    def test_legacy_a_share_fact_cards_show_recovery_path(self):
        source = Path("app.py").read_text(encoding="utf-8")

        self.assertIn("recovery_action = card.get(\"recovery_action\") or {}", source)
        self.assertIn("recovery_action = section.get(\"recovery_action\") or {}", source)
        self.assertIn("恢复路径：{recovery_action.get('action_label')", source)
        self.assertIn("回流：{recovery_action.get('writes_packet')", source)
        self.assertIn("｜DeepSeek：未调用", source)


if __name__ == "__main__":
    unittest.main()
