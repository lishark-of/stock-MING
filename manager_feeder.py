import os
import time
from openai import OpenAI
from supabase import create_client, Client


DEEPSEEK_TOKENS = [
    os.getenv("DEEPSEEK_TOKEN_1"),
    os.getenv("DEEPSEEK_TOKEN_2")
]

DEEPSEEK_TOKENS = [t for t in DEEPSEEK_TOKENS if t]

if not DEEPSEEK_TOKENS:
    raise ValueError("缺少 DEEPSEEK_TOKEN_1 或 DEEPSEEK_TOKEN_2")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL:
    raise ValueError("缺少 SUPABASE_URL")

if not SUPABASE_KEY:
    raise ValueError("缺少 SUPABASE_KEY")

_token_index = 0


def get_deepseek_client():
    global _token_index

    token = DEEPSEEK_TOKENS[_token_index]
    _token_index = (_token_index + 1) % len(DEEPSEEK_TOKENS)

    return OpenAI(
        api_key=token,
        base_url="https://api.deepseek.com/v1"
    )


supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

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
    prompt = f"""
你是一个基金经理研究员。

请从下面资料中，提炼基金经理的投资规则。

这不是普通摘要，你要提炼“可用于选股系统”的规则。

必须输出为多行，每行格式如下：

规则类型|规则内容

规则类型只能从下面选择：
风格
偏好行业
买入条件
卖出条件
风险厌恶
估值标准
仓位纪律
市场适应期
失效风险
风格变化
当前关注
典型语录
其他

提炼要求：
1. 只保留对选股、择时、行业选择、风险控制有用的信息。
2. 如果资料显示他的风格发生变化，必须用【风格变化】标出。
3. 如果资料提到当前市场更适合或不适合他，必须用【市场适应期】标出。
4. 如果资料只是新闻噪音、重复介绍、无实质投资信息，可以只输出：其他|无有效规则。
5. 不要编造资料里没有的内容。
6. 每条规则不超过 80 字。

资料来源：
{source_url}

资料正文：
{text_chunk}
"""

    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {
                "role": "system",
                "content": "你是专业基金经理研究员，擅长从访谈、季报、新闻、持仓说明中提炼投资规则。"
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.15,
        max_tokens=2200
    )

    return response.choices[0].message.content


def save_rules_to_supabase(manager_name, extracted_text, source):
    lines = extracted_text.splitlines()
    saved_count = 0

    for line in lines:
        line = line.strip()

        if not line or "|" not in line:
            continue

        rule_type, content = line.split("|", 1)
        rule_type = rule_type.strip()
        content = content.strip()

        if not content or content == "无有效规则":
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
                "source": source
            }).execute()

            saved_count += 1

        except Exception as e:
            print(f"写入失败：{e}")

    return saved_count


def feed_manager_from_text(manager_name, raw_text, source="自动抓取"):
    print(f"\n开始投喂基金经理：{manager_name}")
    print(f"资料来源：{source}")

    if not raw_text or len(raw_text.strip()) < 200:
        print("资料太短，跳过。")
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
                source_url=source
            )

            saved = save_rules_to_supabase(
                manager_name=manager_name,
                extracted_text=extracted,
                source=source
            )

            total_saved += saved
            print(f"本段写入 {saved} 条规则")

            time.sleep(1)

        except Exception as e:
            print(f"本段处理失败：{e}")

    print(f"完成！总共写入 {total_saved} 条规则。")
    return total_saved
