import os
import time
from openai import OpenAI
from supabase import create_client, Client


# ==============================
# 从环境变量读取密钥
# 不要把真实 key 写进 GitHub
# ==============================
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")


if not DEEPSEEK_API_KEY:
    raise ValueError("缺少 DEEPSEEK_API_KEY")

if not SUPABASE_URL:
    raise ValueError("缺少 SUPABASE_URL")

if not SUPABASE_KEY:
    raise ValueError("缺少 SUPABASE_KEY")


client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com/v1"
)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def split_text_to_chunks(text, chunk_size=5000, overlap=500):
    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append(chunk)

        start = end - overlap

        if start >= len(text):
            break

    return chunks


def extract_rules_with_deepseek(manager_name, text_chunk):
    prompt = f"""
你是一个基金经理研究员。

请从下面资料中，提炼基金经理【{manager_name}】的投资规则。

要求：
1. 只提炼对选股有用的信息。
2. 不要写废话。
3. 每条规则一行。
4. 必须严格使用这个格式：

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
典型语录
其他

资料如下：
{text_chunk}
"""

    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {
                "role": "system",
                "content": "你是专业基金经理研究员，擅长从访谈、研报、持仓说明中提炼投资规则。"
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.2,
        max_tokens=2000
    )

    return response.choices[0].message.content


def save_rules_to_supabase(manager_name, extracted_text, source):
    lines = extracted_text.splitlines()
    saved_count = 0

    for line in lines:
        line = line.strip()

        if not line:
            continue

        if "|" not in line:
            continue

        rule_type, content = line.split("|", 1)

        rule_type = rule_type.strip()
        content = content.strip()

        if not content:
            continue

        try:
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


def feed_manager_from_text(manager_name, raw_text, source="手动投喂"):
    print(f"开始投喂基金经理：{manager_name}")

    chunks = split_text_to_chunks(raw_text)

    print(f"资料已切成 {len(chunks)} 段")

    total_saved = 0

    for i, chunk in enumerate(chunks):
        print(f"正在处理第 {i + 1}/{len(chunks)} 段...")

        extracted = extract_rules_with_deepseek(manager_name, chunk)

        saved = save_rules_to_supabase(
            manager_name=manager_name,
            extracted_text=extracted,
            source=source
        )

        total_saved += saved

        print(f"本段写入 {saved} 条规则")

        time.sleep(1)

    print(f"完成！总共写入 {total_saved} 条规则。")


if __name__ == "__main__":
    manager_name = "刘晓龙"

    text = """
    这里粘贴基金经理资料。
    例如访谈、文章、持仓说明、基金季报里面关于投资思路的文字。
    """

    feed_manager_from_text(
        manager_name=manager_name,
        raw_text=text,
        source="本地测试"
    )
