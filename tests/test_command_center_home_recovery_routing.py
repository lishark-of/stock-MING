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

    def test_home_snapshot_collapses_verbose_diagnostics(self):
        source = Path("visual_components.py").read_text(encoding="utf-8")

        self.assertIn('class="cc-home-details"', source)
        self.assertIn("st.html(html)", source)
        self.assertIn("诊断详情：A股矩阵 / 数据能力控制台 / 原因解释", source)
        self.assertNotIn("旧工具恢复队列", source)
        self.assertNotIn("恢复动作：暂无需要手动恢复的数据源动作", source)

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
