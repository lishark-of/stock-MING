from __future__ import annotations

from typing import Any


DEEPSEEK_DANGEROUS_WORDS = (
    "必买",
    "稳赚",
    "满仓",
    "梭哈",
    "无风险",
    "直接加杠杆",
    "确定上涨",
    "一定反弹",
    "保底收益",
    "低风险高收益",
    "不会亏",
)

DEEPSEEK_SAFETY_REVIEW_MESSAGE = "DeepSeek 解释包含需人工复核的敏感表述。"


def dangerous_words_text() -> str:
    return "、".join(DEEPSEEK_DANGEROUS_WORDS)


def build_deepseek_safety_prompt_clause() -> str:
    return (
        "危险词安全边界：不得使用这些词或等价承诺："
        f"{dangerous_words_text()}。"
        "即使是否定句，也尽量不要写“无风险”；请改写成“风险未完全排除”。"
        "不得建议满仓、梭哈、确定买入、确定上涨或直接加杠杆。"
        "如果你的判断与本地规则结论冲突，必须说明冲突原因，不能覆盖本地规则。"
    )


def find_deepseek_dangerous_words(value: Any) -> list[str]:
    text = "" if value is None else str(value)
    found = [word for word in DEEPSEEK_DANGEROUS_WORDS if word in text]
    return list(dict.fromkeys(found))


def build_deepseek_output_safety_view_model(value: Any) -> dict:
    words = find_deepseek_dangerous_words(value)
    return {
        "has_warning": bool(words),
        "dangerous_words": words,
        "message": DEEPSEEK_SAFETY_REVIEW_MESSAGE if words else "",
    }
