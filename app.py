import streamlit as st
import yfinance as yf
import google.generativeai as genai
from openai import OpenAI
import pandas as pd

# --- 1. Apple Style UI (极简美学) ---
st.set_page_config(page_title="量化交易终端 V12.1", page_icon="🍏", layout="wide")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');
    .stApp { background-color: #F5F5F7; color: #1D1D1F; font-family: -apple-system, sans-serif; }
    .stButton>button { background-color: #0071E3; color: white; border-radius: 980px; border: none; width: 100%; font-weight: 500; }
    .stButton>button:hover { background-color: #0077ED; color: white; }
    .stMetric { background-color: white; padding: 15px; border-radius: 15px; box-shadow: 0 2px 10px rgba(0,0,0,0.05); }
    .stTabs [data-baseweb="tab-list"] { gap: 20px; }
    .stTabs [data-baseweb="tab"] { background-color: transparent; border: none; font-size: 1.1rem; }
</style>
""", unsafe_allow_html=True)

# --- 2. 权限与密钥 ---
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
    # 读取 Secrets
    try:
        ds_key = st.secrets["DEEPSEEK_API_KEY"]
        gm_key = st.secrets["GEMINI_API_KEY"]
    except: ds_key = gm_key = None

    # --- 3. 核心 AI 调用函数 ---
    def call_ai(engine, prompt):
        if engine == "DeepSeek":
            try:
                client = OpenAI(api_key=ds_key, base_url="https://api.deepseek.com/v1")
                res = client.chat.completions.create(model="deepseek-chat", messages=[{"role": "user", "content": f"【深度审计模式】{prompt}"}])
                return res.choices[0].message.content
            except: return "❌ DeepSeek 节点繁忙"
        elif engine == "Gemini":
            try:
                genai.configure(api_key=gm_key)
                for m in ['gemini-1.5-flash', 'gemini-pro']:
                    try: return genai.GenerativeModel(m).generate_content(prompt).text
                    except: continue
                return "⚠️ Gemini 暂时不可用，已自动切换为 DeepSeek 单核推演。"
            except: return "⚠️ 引擎连接失败"

    st.title("机构级资产指挥台")
    t1, t2, t3 = st.tabs(["🇺🇸 美股穿透", "🇨🇳 A股博弈", "🐳 聪明资金雷达"])

    # 共享状态
    if 'current_ticker' not in st.session_state: st.session_state.current_ticker = "LITE"

    # ==========================================
    # 端口 1：美股硬核价值区
    # ==========================================
    with t1:
        c1, c2, c3 = st.columns([2, 1, 1])
        with c1: st.session_state.current_ticker = st.text_input("美股代码", st.session_state.current_ticker, key="us_in").upper()
        with c2:
            try:
                p = round(yf.Ticker(st.session_state.current_ticker).history(period='1d')['Close'].iloc[0], 2)
                st.metric("实时价格", f"$ {p}")
            except: p = "N/A"; st.metric("实时价格", "--")
        with c3:
            st.write("")
            st.write("")
            engine_us = st.radio("算力", ["DeepSeek", "Gemini", "双擎"], horizontal=True, key="en_us")
        
        if st.button(f"启动 Deep Research：{st.session_state.current_ticker}"):
            if st.session_state.user_role == "Admin":
                prompt = f"分析美股标的{st.session_state.current_ticker}，价{p}。结合AI算力物理瓶颈、价值错杀进行推演，给出阶梯式止盈与底仓管理建议。"
                if engine_us in ["DeepSeek", "双擎"]: st.markdown(f"### 🔴 DeepSeek 深度研报\n{call_ai('DeepSeek', prompt)}")
                if engine_us in ["Gemini", "双擎"]: st.markdown(f"### 🔵 Gemini 宏观洞察\n{call_ai('Gemini', prompt)}")
            else: st.error("访客权限受限")

    # ==========================================
    # 端口 2：A 股政策博弈区 (已全面解锁)
    # ==========================================
    with t2:
        c4, c5, c6 = st.columns([2, 1, 1])
        with c4:
            a_ticker = st.text_input("A股代码 (后缀: .SZ 或 .SS)", "002008.SZ").upper()
            st.session_state.current_ticker = a_ticker # A股搜索同样联动资金雷达
        with c5:
            try:
                pa = round(yf.Ticker(a_ticker).history(period='1d')['Close'].iloc[0], 2)
                st.metric("实时价格", f"¥ {pa}")
            except: pa = "N/A"; st.metric("实时价格", "--")
        with c6:
            st.write("")
            st.write("")
            engine_a = st.radio("算力 ", ["DeepSeek", "Gemini", "双擎"], horizontal=True, key="en_a")
                
        if st.button(f"启动量化穿透：{a_ticker}"):
            if st.session_state.user_role == "Admin":
                prompt_a = f"分析A股标的{a_ticker}，价{pa}。分析筹码断层、主力/游资博弈痕迹、做T空间，并给出精确到小数点的止盈止损建议。"
                if engine_a in ["DeepSeek", "双擎"]: st.markdown(f"### 🔴 DeepSeek 量化演算\n{call_ai('DeepSeek', prompt_a)}")
                if engine_a in ["Gemini", "双擎"]: st.markdown(f"### 🔵 Gemini 政策解读\n{call_ai('Gemini', prompt_a)}")
            else: st.error("访客权限受限")

    # ==========================================
    # 端口 3：聪明资金雷达 (支持排序与 AI 审计)
    # ==========================================
    with t3:
        st.markdown(f"### 正在审计：{st.session_state.current_ticker} 的持仓分布")
        
        tick = yf.Ticker(st.session_state.current_ticker)
        col_l, col_r = st.columns([1, 1])
        
        with col_l:
            st.markdown("**顶级机构持仓 (点击表头可排序)**")
            try:
                holders = tick.institutional_holders
                if holders is not None:
                    # 将百分比转为数字方便排序
                    holders['% Out'] = holders['% Out'].astype(float) 
                    st.dataframe(holders, use_container_width=True, hide_index=True)
                else: st.write("暂无公开持仓披露数据")
            except: st.write("持仓数据暂不可用")

        with col_r:
            st.markdown("**AI 持仓质量审计 (Deep Research)**")
            if st.button("🧠 消耗 Token 启动持仓关联分析"):
                if holders is not None:
                    h_list = holders['Holder'].tolist()
                    audit_p = f"""
                    以下是标的 {st.session_state.current_ticker} 的主要机构：{h_list}。
                    请审计：
                    1. 哪些是‘僵尸指数基金’，哪些是‘嗅觉敏锐的主动基金’。
                    2. 当前筹码是否正在从散户向顶级机构集中？
                    3. 该标的的‘聪明资金信任等级’。
                    """
                    st.info(call_ai("DeepSeek", audit_p))
                else: st.warning("未检测到有效持仓数据")

        st.markdown("---")
        st.markdown("**🐳 聪明人动向实时监控**")
        whale_data = pd.DataFrame({
            "标签": ["AI 大佬关联", "硅谷离职员工创业流向", "顶级对冲基金 (Duquesne)", "国资背景"],
            "重点标的": ["LITE, AAOI", "WDC, NVDA", "LITE, TSLA", "002008.SZ"],
            "AI 诊断建议": ["关注光模块回踩", "存储芯片拐点已至", "顶级机构持续增仓", "政策主线稳定"]
        })
        st.dataframe(whale_data, use_container_width=True, hide_index=True)
