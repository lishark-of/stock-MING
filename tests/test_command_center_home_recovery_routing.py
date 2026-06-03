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


class CommandCenterHomeRecoveryRoutingTests(unittest.TestCase):
    def test_home_diagnostic_recovery_routes_chip_and_hard_risk(self):
        tokens = _function_tokens("render_home_a_share_diagnostic_recovery_controls")

        self.assertIn("chip_radar", tokens)
        self.assertIn("hard_risk", tokens)
        self.assertIn("_run_manual_chip_radar_capability_check", tokens)
        self.assertIn("_run_manual_hard_risk_capability_check", tokens)
        self.assertIn("btn_cc_home_a_share_diagnostic_recovery_", tokens)

    def test_a_share_capability_controls_include_hard_risk_check(self):
        tokens = _function_tokens("render_a_share_data_capability_controls")

        self.assertIn("hard_risk_capability_check", tokens)
        self.assertIn("检测公告硬风险", tokens)
        self.assertIn("_run_manual_hard_risk_capability_check", tokens)


if __name__ == "__main__":
    unittest.main()
