import unittest

import deepseek_safety
import margin_etf_research
import next_stock_radar


class DeepSeekSafetyTests(unittest.TestCase):
    def test_dangerous_word_list_contains_trading_risk_terms(self):
        words = set(deepseek_safety.DEEPSEEK_DANGEROUS_WORDS)

        for word in ["必买", "稳赚", "满仓", "梭哈", "无风险", "直接加杠杆", "确定上涨", "一定反弹", "保底收益", "低风险高收益", "不会亏"]:
            self.assertIn(word, words)

    def test_prompt_clause_forbids_dangerous_words_and_rewrites_no_risk(self):
        clause = deepseek_safety.build_deepseek_safety_prompt_clause()

        self.assertIn("不得使用这些词", clause)
        self.assertIn("风险未完全排除", clause)
        self.assertIn("不得建议满仓", clause)
        for word in deepseek_safety.DEEPSEEK_DANGEROUS_WORDS:
            self.assertIn(word, clause)

    def test_output_safety_marks_dangerous_words(self):
        view_model = deepseek_safety.build_deepseek_output_safety_view_model(
            "这不是建议，但原文出现无风险、满仓、稳赚、梭哈等词。"
        )

        self.assertTrue(view_model["has_warning"])
        self.assertIn("无风险", view_model["dangerous_words"])
        self.assertIn("满仓", view_model["dangerous_words"])
        self.assertIn("稳赚", view_model["dangerous_words"])
        self.assertIn("梭哈", view_model["dangerous_words"])
        self.assertIn("需人工复核", view_model["message"])

    def test_output_safety_does_not_mark_normal_explanation(self):
        view_model = deepseek_safety.build_deepseek_output_safety_view_model(
            "本地规则结论为只观察，等待数据验证后再评估。"
        )

        self.assertFalse(view_model["has_warning"])
        self.assertEqual(view_model["dangerous_words"], [])

    def test_next_ticket_safety_flags_without_removing_original_text(self):
        payload = {"one_sentence_conclusion": "这类表述可能写成无风险或满仓，需要复核。"}

        sanitized, found = next_stock_radar.sanitize_deepseek_result(payload)

        self.assertEqual(sanitized["one_sentence_conclusion"], payload["one_sentence_conclusion"])
        self.assertIn("无风险", found)
        self.assertIn("满仓", found)

    def test_margin_etf_prompt_includes_safety_clause(self):
        prompt = margin_etf_research.build_margin_etf_research_prompt({"allocation_result": {"action_state": "观察"}})

        self.assertIn("危险词安全边界", prompt)
        self.assertIn("不得建议满仓", prompt)
        self.assertIn("风险未完全排除", prompt)


if __name__ == "__main__":
    unittest.main()
