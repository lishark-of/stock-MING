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
        self.assertIn("最近恢复结果", source)
        self.assertIn("最近恢复影响", source)
        self.assertIn("latest_evidence_impact", source)
        self.assertIn("external_call_policy", source)
        self.assertIn("DeepSeek：未调用", source)

    def test_decision_and_strategy_cards_surface_projection_confidence(self):
        source = Path("visual_components.py").read_text(encoding="utf-8")

        self.assertIn("projection_confidence_summary", source)
        self.assertIn("路径：{escape(str(projection_confidence.get(\"label\") or \"路径待生成\"))}", source)
        self.assertIn("趋势推演门槛", source)
        self.assertIn("路径只做条件化推演，不直接决定仓位", source)

    def test_home_snapshot_renders_recovery_priority_lanes(self):
        source = Path("visual_components.py").read_text(encoding="utf-8")

        self.assertIn("priority_lanes", source)
        self.assertIn("recovery_priority_html", source)
        self.assertIn("recovery_priority_items", source)
        self.assertIn("恢复优先级影响", source)
        self.assertIn("legacy_migration_map", source)
        self.assertIn("旧版能力迁移地图", source)
        self.assertIn("valid_legacy_migration_actions", source)
        self.assertIn("迁移地图｜打开旧工具", source)
        self.assertIn("completion_checks", source)
        self.assertIn("完成条件", source)
        self.assertIn("P0 权限/本会话跳过", Path("command_center_home_snapshot.py").read_text(encoding="utf-8"))
        self.assertIn("P1 缓存/近期无数据", Path("command_center_home_snapshot.py").read_text(encoding="utf-8"))
        self.assertIn("P2 旧工具 packet 迁移", Path("command_center_home_snapshot.py").read_text(encoding="utf-8"))

    def test_home_snapshot_renders_provider_diagnostic_cards(self):
        source = Path("visual_components.py").read_text(encoding="utf-8")

        self.assertIn("provider_diagnostic_cards", source)
        self.assertIn("provider_diagnostic_html", source)
        self.assertIn("诊断结论", source)
        self.assertIn("interface_diagnostic_items", source)
        self.assertIn("interface_diagnostic_html", source)
        self.assertIn("接口诊断待生成", source)
        self.assertIn("接口原因", source)
        self.assertIn("按钮说明", source)
        self.assertIn("recovery_button_context", source)
        self.assertIn("为什么搜不到", source)

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
        self.assertIn("权限不足：", source)
        self.assertIn("本会话跳过：", source)
        self.assertIn("近期无数据：", source)

    def test_home_snapshot_renders_recovered_evidence_modules(self):
        source = Path("visual_components.py").read_text(encoding="utf-8")

        self.assertIn("recovered_evidence_modules", source)
        self.assertIn("已回流模块", source)
        self.assertIn("暂无已回流证据模块", source)

    def test_home_snapshot_collapses_verbose_diagnostics(self):
        source = Path("visual_components.py").read_text(encoding="utf-8")

        self.assertIn('class="cc-home-details"', source)
        self.assertIn("st.html(html)", source)
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
