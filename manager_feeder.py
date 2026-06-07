import hashlib
import time

from openai import OpenAI
from supabase import create_client, Client

from config import get_deepseek_keys, require_supabase_config
from deepseek_safety import (
    DEEPSEEK_SAFETY_REVIEW_MESSAGE,
    build_deepseek_safety_prompt_clause,
    find_deepseek_dangerous_words,
)


DEEPSEEK_TOKENS = get_deepseek_keys()
SUPABASE_URL, SUPABASE_KEY = require_supabase_config()

_token_index = 0


def get_deepseek_client():
    global _token_index

    if not DEEPSEEK_TOKENS:
        return None

    token = DEEPSEEK_TOKENS[_token_index]
    _token_index = (_token_index + 1) % len(DEEPSEEK_TOKENS)

    return OpenAI(
        api_key=token,
        base_url="https://api.deepseek.com/v1",
    )


supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

ALLOWED_RULE_TYPES = {
    "当前关注",
    "风格变化",
    "持仓变化",
    "行业判断",
    "买入条件",
    "风险厌恶",
    "宏观判断",
    "市场适应期",
    "典型语录",
    "其他",
}


def split_text_to_chunks(text, chunk_size=6000, overlap=500):
    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        start = end - overlap

        if start >= len(text):
            break

    return chunks


def extract_rules_with_deepseek(manager_name, text_chunk, source_url=""):
    if not DEEPSEEK_TOKENS:
        summary = " ".join((text_chunk or "").split())[:180]
        return f"其他|needs_ai_extract：未调用模型，仅保存原始摘要/待提炼状态。来源 {source_url} 摘要 {summary}"

    prompt = f"""
你是一个基金经理研究员。

请从下面资料中，提炼基金经理的投资规则。

这不是普通摘要，你要提炼“可用于选股系统”的规则。
资料可能只有标题、RSS摘要、发布时间和链接；只要其中包含投资含义，也必须提炼。

必须输出为多行，每行格式如下：

rule_type|content

rule_type 只能从下面选择：
当前关注
风格变化
持仓变化
行业判断
买入条件
风险厌恶
宏观判断
市场适应期
典型语录
其他

提炼要求：
1. 即使资料只有标题、摘要或很短，也必须尝试提炼。
2. 如果标题或摘要包含基金经理观点、持仓变化、行业判断、市场判断，必须输出规则。
3. 不要因为资料短就直接输出“无有效规则”。
4. 只有完全没有投资含义时，才输出：其他|无有效规则。
5. 只保留对选股、择时、行业选择、风险控制有用的信息。
6. 如果资料显示风格发生变化，必须用“风格变化”。
7. 如果资料提到当前市场更适合或不适合该经理，必须用“市场适应期”。
8. 如果资料提到加仓、减仓、重仓、调仓，必须用“持仓变化”。
9. 如果资料提到某个行业机会或风险，必须用“行业判断”。
10. 不要编造资料里没有的内容。
11. 每条规则不超过 80 字。

示例：
当前关注|曲少杰认为港股估值进入放心区间，高毛利优质资产仍稀缺
持仓变化|张坤一季度增持阿斯麦和SK海力士，消费框架外扩至全球科技资产
行业判断|Leopold更关注AI算力、电力、数据中心和基础设施链条
风险厌恶|丘栋荣提示高股息策略并非低风险，需警惕拥挤交易
宏观判断|Ray Dalio认为黄金快速上涨反映市场对宏观风险的担忧

资料来源：
{source_url}

资料正文：
{text_chunk}
"""

    retry_delays = [3, 6, 10]

    for attempt, delay in enumerate(retry_delays, start=1):
        try:
            client = get_deepseek_client()
            if client is None:
                return "其他|needs_ai_extract：未调用模型，仅保存原始摘要/待提炼状态。"

            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {
                        "role": "system",
                        "content": "你是专业基金经理研究员，擅长从访谈、季报、新闻标题、RSS摘要、持仓说明中提炼投资规则；不得编造资料外信息。\n"
                        + build_deepseek_safety_prompt_clause(),
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                temperature=0.15,
                max_tokens=2200,
            )

            content = response.choices[0].message.content
            dangerous_words = find_deepseek_dangerous_words(content)
            if dangerous_words:
                print(f"{DEEPSEEK_SAFETY_REVIEW_MESSAGE} 命中：{'、'.join(dangerous_words)}")
            return content

        except Exception as e:
            print(f"DeepSeek 调用失败，第 {attempt} 次重试：{e}")
            time.sleep(delay)

    print("DeepSeek 连续失败，返回无有效规则。")
    return "其他|无有效规则"


def save_rules_to_supabase(manager_name, extracted_text, source):
    lines = extracted_text.splitlines()
    saved_count = 0

    for line in lines:
        line = line.strip()

        if not line or "|" not in line:
            continue

        line = line.lstrip("-*0123456789.、 ")
        rule_type, content = line.split("|", 1)
        rule_type = rule_type.strip()
        content = content.strip()

        if rule_type not in ALLOWED_RULE_TYPES:
            rule_type = "其他"

        if not content or "无有效规则" in content:
            continue

        rule_hash = hashlib.sha256(
            f"{manager_name}|{rule_type}|{content}".encode("utf-8")
        ).hexdigest()

        try:
            existed = (
                supabase
                .table("manager_rules")
                .select("id")
                .eq("manager_name", manager_name)
                .eq("content", content)
                .limit(1)
                .execute()
            )

            if existed.data:
                continue

            supabase.table("manager_rules").insert({
                "manager_name": manager_name,
                "rule_type": rule_type,
                "content": content,
                "source": source,
            }).execute()

            saved_count += 1
            print(f"写入规则成功：{rule_hash[:8]}｜{rule_type}｜{content}")

        except Exception as e:
            print(f"写入失败：{e}")

    return saved_count


def feed_manager_from_text(manager_name, raw_text, source="自动抓取"):
    print(f"\n开始投喂基金经理：{manager_name}")
    print(f"资料来源：{source}")

    if not raw_text or not raw_text.strip():
        print("资料为空，跳过。")
        return 0

    chunks = split_text_to_chunks(raw_text)
    print(f"资料已切成 {len(chunks)} 段")

    total_saved = 0

    for i, chunk in enumerate(chunks):
        print(f"正在处理第 {i + 1}/{len(chunks)} 段...")

        try:
            extracted = extract_rules_with_deepseek(
                manager_name=manager_name,
                text_chunk=chunk,
                source_url=source,
            )

            saved = save_rules_to_supabase(
                manager_name=manager_name,
                extracted_text=extracted,
                source=source,
            )

            total_saved += saved
            print(f"本段写入 {saved} 条规则")

            time.sleep(1)

        except Exception as e:
            print(f"本段处理失败：{e}")

    print(f"完成！总共写入 {total_saved} 条规则。")
    return total_saved
