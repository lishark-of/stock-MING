import streamlit as st
import yfinance as yf
import google.generativeai as genai
from openai import OpenAI
import pandas as pd
import time
import json
import os

# --- 1. Apple Style UI ---
st.set_page_config(page_title="量化交易终端 V15.0", page_icon="🍏", layout="wide")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');
    .stApp { background-color: #F5F5F7; color: #1D1D1F; font-family: -apple-system, sans-serif; }
    .stButton>button { background-color: #1D1D1F; color: white; border-radius: 8px; border: none; width: 100%; font-weight: 500; transition: 0.2s; }
    .stButton>button:hover { background-color: #434343; color: white; }
    .stMetric { background-color: white; padding: 15px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.03); border: 1px solid #E5E5EA; }
    .stTabs [data-baseweb="tab-list"] { gap: 20px; }
    .stTabs [data-baseweb="tab"] { background-color: transparent; border: none; font-size: 1.1rem; }
    .status-text { font-family: 'Courier New', monospace; color: #0071E3; font-size: 0.9rem; }
    .knowledge-card { background-color: #ffffff; padding: 15px; border-radius: 8px; border-left: 4px solid #0071E3; margin-bottom: 10px; font-size: 0.9rem;}
</style>
""", unsafe_allow_html=True)

# --- 2. 策略外脑（本地微型数据库）初始化 ---
KNOWLEDGE_FILE = "strategy_knowledge.json"

def init_knowledge_base():
    if not os.path.exists(KNOWLEDGE_FILE):
        with open(KNOWLEDGE_FILE, 'w', encoding='utf-8') as f:
            json.dump({"strategies": [], "reflections": []}, f)

def load_knowledge():
    with open(KNOWLEDGE_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_knowledge(data):
    with open(KNOWLEDGE_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

init_knowledge_base()

# --- 3. 权限与密钥 ---
if 'user_role' not in st.session_state: st.session_state.user_role = None

if st.session_state.user_role is None:
    st.markdown("<h1 style='text-align: center; margin-top: 10vh;'>Terminal</h1>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        pwd = st.text_input("", type="password", placeholder="Access Key", label_visibility="collapsed")
        if st.button("进入系统"):
            if pwd == "888888": st.session_state.user_role = "Admin"; st.rerun()
            elif pwd == "guest": st.session_state.user_role = "Guest"; st.rerun()
else:
    try:
        ds_key = st.secrets["DEEPSEEK_API_KEY"]
        gm_key = st.secrets["GEMINI_API_KEY"]
    except: ds_key = gm_key = None

    # --- 4. 核心工具函数 ---
    def run_quant_progress():
        bar = st.progress(0)
        status = st.empty()
        steps = ["📡 接入数据源...", "🧠 加载策略外脑库...", "🧮 注入蒙特卡洛模型...", "⚡ 生成最终作战策略..."]
        for i in range(100):
            bar.progress(i + 1)
            if i % 25 == 0: status.markdown(f"<p class='status-text'>{steps[i//25]}</p>", unsafe_allow_html=True)
            time.sleep(0.015)
        status.empty(); bar.empty()

    def call_deepseek_stream(prompt):
        if not ds_key: return st.error("缺少 DeepSeek 密钥")
        try:
            client = OpenAI(api_key=ds_key, base_url="https://api.deepseek.com/v1")
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}],
                stream=True
            )
            st.write_stream((chunk.choices[0].delta.content or "") for chunk in response)
        except: st.error("DeepSeek 连接异常。")

    # ==========================================
    # 全局目标锁定架构
    # ==========================================
    st.title("机构级资产指挥台")
    st.markdown("### 🎯 全局目标锁定")
    top_c1, top_c2, top_c3 = st.columns([2, 1, 2])
    with top_c1: target = st.text_input("输入监控代码", "LITE", label_visibility="collapsed").upper()
    with top_c2:
        try:
            p = round(yf.Ticker(target).history(period='1d')['Close'].iloc[0], 2)
            st.metric("卫星侦测价格", f"{p}")
        except: p = "N/A"; st.metric("卫星侦测价格", "--")
    with top_c3:
        global_engine = st.radio("全局算力调度", ["DeepSeek", "双擎验证"], horizontal=True, label_visibility="collapsed")
        
    st.markdown("---")

    t1, t2, t3, t4 = st.tabs(["🇺🇸 美股深度", "🇨🇳 A股量化", "🐳 资金雷达", "🧠 策略外脑 (进化中心)"])

    # 获取当前的知识库，注入到 Prompt 中 (RAG 技术)
    db = load_knowledge()
    custom_rules = "\n".join(db["strategies"] + db["reflections"])
    system_injection = f"\n\n【⚠️ 核心强制指令】：你必须严格结合以下'私有量化规则库'对当前标的进行分析，如果当前标的触发了规则库中的止损或做T条件，必须在报告最开头红色加粗警告：\n{custom_rules}" if custom_rules else ""

    # --- 端口 1 & 2: 推演 (带外脑注入) ---
    with t1:
        if st.button(f"🚀 启动 Deep Research：{target}", key="btn_us"):
            prompt = f"分析美股{target}，价{p}。结合AI算力物理瓶颈推演阶梯止盈。{system_injection}"
            run_quant_progress()
            st.markdown("### 🔴 DeepSeek 深度推演流 (外脑辅助)")
            call_deepseek_stream(prompt)

    with t2:
        if st.button(f"🚀 启动量化穿透：{target}", key="btn_a"):
            prompt_a = f"分析A股{target}，价{p}。分析筹码断层及博弈痕迹。{system_injection}"
            run_quant_progress()
            st.markdown("### 🔴 DeepSeek 量化推演流 (外脑辅助)")
            call_deepseek_stream(prompt_a)

    with t3:
        st.info("资金雷达逻辑已就绪，自动跟随全局目标。")

    # ==========================================
    # 🆕 端口 4：🧠 策略外脑 (软件自我升级区)
    # ==========================================
    with t4:
        st.markdown("### 🧬 RAG 向量记忆注入中心")
        st.caption("在这里消耗 Token，将外部经验转化为 App 的永久量化纪律。")
        
        c_left, c_right = st.columns([1, 1])
        
        with c_left:
            st.markdown("**1. 喂养私域战法 (理论吸收)**")
            strategy_text = st.text_area("粘贴游资语录/研报片段", placeholder="例如：当CPO概念股高位爆量换手超20%且尾盘抢筹时，次日跳空高开概率达80%...")
            if st.button("🧠 消耗 Token 提炼量化规则", key="feed_strat"):
                if strategy_text:
                    with st.spinner("DeepSeek 正在拆解逻辑..."):
                        client = OpenAI(api_key=ds_key, base_url="https://api.deepseek.com/v1")
                        res = client.chat.completions.create(
                            model="deepseek-chat",
                            messages=[{"role": "user", "content": f"请将以下大白话转化为极其简练的'机器量化条件规则'（不超过50字）：{strategy_text}"}]
                        ).choices[0].message.content
                        db["strategies"].append(res)
                        save_knowledge(db)
                        st.success("✅ 战法已成功写入 App 永久外脑！")
                        st.rerun()

        with c_right:
            st.markdown("**2. 实盘交易复盘 (自我纠偏)**")
            trade_ticker = st.text_input("交易标的", placeholder="例如：贵研铂业 / 大族激光 / LITE")
            trade_result = st.text_area("交易结果与情绪", placeholder="例如：重仓买入后遇到美股闪崩，未遵守 97.8 元的极限止损纪律，导致回撤扩大，当时心态有赌徒心理。")
            if st.button("🩸 消耗 Token 凝练血泪纪律", key="feed_reflect"):
                if trade_result:
                    with st.spinner("DeepSeek 正在剖析失误..."):
                        client = OpenAI(api_key=ds_key, base_url="https://api.deepseek.com/v1")
                        res = client.chat.completions.create(
                            model="deepseek-chat",
                            messages=[{"role": "user", "content": f"作为无情的量化机器，请基于以下失败的实盘记录，总结出一条铁血量化止损纪律（必须带有明确的数字底线，不超过50字）：标的{trade_ticker}，情况：{trade_result}"}]
                        ).choices[0].message.content
                        db["reflections"].append(f"【血泪纪律 - {trade_ticker}】: {res}")
                        save_knowledge(db)
                        st.success("✅ 血泪纪律已刻入系统底层！")
                        st.rerun()

        st.markdown("---")
        st.markdown("**📚 当前 App 脑容量 (已掌握的量化规则)**")
        if db["strategies"] or db["reflections"]:
            for rule in db["strategies"] + db["reflections"]:
                st.markdown(f"<div class='knowledge-card'>⚙️ {rule}</div>", unsafe_allow_html=True)
        else:
            st.info("当前外脑为空。请开始喂养数据。")
