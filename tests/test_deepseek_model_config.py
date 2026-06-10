import ast
import os
import unittest
from pathlib import Path

import command_center_next_session_projection as next_session_projection
import command_center_projection as projection
import config
from server.services import model_strategy_service


class DeepSeekModelConfigTests(unittest.TestCase):
    def setUp(self):
        self._original_env = {
            key: os.environ.get(key)
            for key in ("DEEPSEEK_DEFAULT_MODEL", "DEEPSEEK_EXPLAIN_MODEL", "DEEPSEEK_FAST_MODEL")
        }
        self._original_loader = config._load_local_streamlit_secrets
        self._original_streamlit_secret = config._get_streamlit_secret
        config._load_local_streamlit_secrets = lambda: {}
        config._get_streamlit_secret = lambda name, default=None: default
        for key in self._original_env:
            os.environ.pop(key, None)

    def tearDown(self):
        for key, value in self._original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        config._load_local_streamlit_secrets = self._original_loader
        config._get_streamlit_secret = self._original_streamlit_secret

    def test_default_strategy_uses_pro_for_explain_and_flash_for_fast(self):
        self.assertEqual(config.get_deepseek_model("default"), "deepseek-v4-pro")
        self.assertEqual(config.get_deepseek_model("explain"), "deepseek-v4-pro")
        self.assertEqual(config.get_deepseek_model("projection"), "deepseek-v4-pro")
        self.assertEqual(config.get_deepseek_model("fast"), "deepseek-v4-flash")
        self.assertEqual(config.get_deepseek_model("healthcheck"), "deepseek-v4-flash")

        strategy = config.get_deepseek_model_strategy()

        self.assertEqual(strategy["explain"], "deepseek-v4-pro")
        self.assertEqual(strategy["fast"], "deepseek-v4-flash")
        self.assertFalse(strategy["contains_secret"])

    def test_env_overrides_model_strategy_without_hardcoded_callsite_names(self):
        os.environ["DEEPSEEK_DEFAULT_MODEL"] = "custom-default"
        os.environ["DEEPSEEK_EXPLAIN_MODEL"] = "custom-explain"
        os.environ["DEEPSEEK_FAST_MODEL"] = "custom-fast"

        self.assertEqual(config.get_deepseek_model("default"), "custom-default")
        self.assertEqual(config.get_deepseek_model("explain"), "custom-explain")
        self.assertEqual(config.get_deepseek_model("projection"), "custom-explain")
        self.assertEqual(config.get_deepseek_model("feeder"), "custom-fast")
        self.assertEqual(config.get_deepseek_model("healthcheck"), "custom-fast")

    def test_model_strategy_reference_helper_is_configurable_and_secret_free(self):
        os.environ["DEEPSEEK_DEFAULT_MODEL"] = "custom-default"
        os.environ["DEEPSEEK_EXPLAIN_MODEL"] = "custom-explain"

        factor_ref = model_strategy_service.build_deepseek_model_strategy_ref("factor_explain")
        fallback_ref = model_strategy_service.build_deepseek_model_strategy_ref("unknown-purpose")

        self.assertEqual(factor_ref["purpose"], "factor_explain")
        self.assertEqual(factor_ref["model"], "custom-explain")
        self.assertIn("DEEPSEEK_EXPLAIN_MODEL", factor_ref["config_keys"])
        self.assertEqual(factor_ref["active_config_key"], "DEEPSEEK_EXPLAIN_MODEL")
        self.assertTrue(factor_ref["uses_configured_value"])
        self.assertTrue(factor_ref["does_not_hardcode_model"])
        self.assertFalse(factor_ref["contains_secret"])

        self.assertEqual(fallback_ref["purpose"], "default")
        self.assertEqual(fallback_ref["model"], "custom-default")
        self.assertIn("DEEPSEEK_DEFAULT_MODEL", fallback_ref["config_keys"])

    def test_projection_merges_default_to_configured_model(self):
        os.environ["DEEPSEEK_EXPLAIN_MODEL"] = "custom-projection-model"

        packet = projection.merge_deepseek_projection_overlay(
            {"paths": [{"name": "乐观路径"}, {"name": "中性路径"}, {"name": "谨慎路径"}]},
            {"paths": []},
            raw_text="{}",
        )
        self.assertEqual(packet["deepseek_projection"]["model"], "custom-projection-model")

        next_packet = next_session_projection.merge_deepseek_next_session_projection(
            {"packet_key": "command_center_next_session_projection_packet"},
            "{}",
        )
        self.assertEqual(next_packet["deepseek_synthesis"]["model"], "custom-projection-model")

    def test_deepseek_model_names_are_centralized_outside_docs_and_tests(self):
        root = Path(__file__).resolve().parents[1]
        allowed = {
            root / "config.py",
            Path(__file__).resolve(),
            root / "docs" / "command_center_3_architecture.md",
        }
        source_suffixes = {".py", ".ts", ".tsx", ".js", ".jsx"}
        forbidden_fragments = ("deepseek-chat", "deepseek-v4-pro", "deepseek-v4-flash")
        offenders = []

        for path in root.rglob("*"):
            if path in allowed or path.suffix not in source_suffixes:
                continue
            if any(part in {".git", ".venv", "__pycache__", "node_modules", "dist"} for part in path.parts):
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for fragment in forbidden_fragments:
                if fragment in text:
                    offenders.append(f"{path.relative_to(root)} contains {fragment}")

        self.assertEqual(offenders, [])

    def test_chat_completion_calls_use_configured_deepseek_model(self):
        root = Path(__file__).resolve().parents[1]
        offenders = []

        def attr_chain(node):
            parts = []
            while isinstance(node, ast.Attribute):
                parts.append(node.attr)
                node = node.value
            if isinstance(node, ast.Name):
                parts.append(node.id)
            return list(reversed(parts))

        for path in root.rglob("*.py"):
            if any(part in {".git", ".venv", "__pycache__", "node_modules", "dist"} for part in path.parts):
                continue
            if path.parts[-2:-1] == ("tests",):
                continue

            text = path.read_text(encoding="utf-8", errors="ignore")
            try:
                tree = ast.parse(text)
            except SyntaxError as exc:
                offenders.append(f"{path.relative_to(root)} cannot be parsed: {exc}")
                continue

            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                chain = attr_chain(node.func)
                if chain[-3:] != ["chat", "completions", "create"]:
                    continue

                model_keywords = [kw for kw in node.keywords if kw.arg == "model"]
                if model_keywords:
                    for keyword in model_keywords:
                        value_source = ast.get_source_segment(text, keyword.value) or ""
                        if "get_deepseek_model(" not in value_source:
                            offenders.append(
                                f"{path.relative_to(root)}:{node.lineno} model is not from get_deepseek_model"
                            )
                    continue

                has_kwargs = any(kw.arg is None for kw in node.keywords)
                if has_kwargs and (
                    '"model": get_deepseek_model(' in text or "'model': get_deepseek_model(" in text
                ):
                    continue

                offenders.append(f"{path.relative_to(root)}:{node.lineno} missing configured model keyword")

        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
