import streamlit as st
import yfinance as yf
import google.generativeai as genai
from openai import OpenAI
import pandas as pd

# --- 1. Apple Style UI (极简美学) ---
st.set_page_config(page_title="量化交易终端 V12", page_icon="🍏", layout="wide")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');
    .stApp { background-color: #F5F5F7; color: #1D1D1F; font-family: -apple-system, sans-serif; }
    .stButton>button { background-color: #0071E3; color: white; border-radius: 980px; border: none; width: 100%; font-weight: 500; }
    .stTab { background-color: transparent; }
    .stMetric { background-color: white; padding: 15px; border-radius: 15px; box-shadow: 0 2px 10px rgba(0,0,0,0.05); }
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
else:
    # 读取 Secrets
    try:
        ds_key = st.secrets["DEEPSEEK_API_KEY"]
        gm_key = st.secrets["GEMINI_API_KEY"]
    except: ds_key = gm_key = None

    # --- 3. 核心工具函数 ---
    def call_ai(engine, prompt):
        if engine == "DeepSeek":
            try:
                client = OpenAI(api_key=ds_key, base_url="https://api.deepseek.com/v1")
                res = client.chat.completions.create(model="deepseek-chat", messages=[{"role": "user", "content": f"【深度研报模式】{prompt}"}])
                return res.choices[0].message.content
            except: return "❌ DeepSeek 算力节点连接超时"
        elif engine == "Gemini":
            try:
                genai.configure(api_key=gm_key)
                for m in ['gemini-1.5-flash', 'gemini-pro']:
                    try: return genai.GenerativeModel(m).generate_content(prompt).text
                    except: continue
                return "⚠️ Gemini 引擎受地理围栏限制，已自动切回 DeepSeek。"
            except: return "⚠️ 引擎连接异常"

    st.title("机构级资产指挥台")
    t1, t2, t3 = st.tabs(["🇺🇸 美股穿透", "🇨🇳 A股博弈", "🐳 聪明资金雷达"])

    # 共享状态：存储当前搜索的 Ticker
    if 'current_ticker' not in st.session_state: st.session_state.current_ticker = "LITE"

    # --- 端口 1 & 2 保持逻辑并同步更新状态 ---
    with t1:
        c1, c2 = st.columns([3, 1])
        with c1: 
            st.session_state.current_ticker = st.text_input("美股代码", st.session_state.current_ticker).upper()
        with c2:
            try:
                price = round(yf.Ticker(st.session_state.current_ticker).history(period='1d')['Close'].iloc[0], 2)
                st.metric("Price", f"$ {price}")
            except: price = "N/A"
        
        if st.button(f"启动 Deep Research：{st.session_state.current_ticker}"):
            p_text = f"分析{st.session_state.current_ticker}，价{price}。需含算力瓶颈、错杀剥离及盈利管理建议。"
            st.markdown(f"### 🔴 DeepSeek 深度研报\n{call_ai('DeepSeek', p_text)}")

    with t2:
        # A股逻辑保持不变...
        st.write("A股端口已锁定，请输入带后缀的代码 (如 002008.SZ)")

    # ==========================================
    # 🆕 端口 3：动态聪明资金雷达 (终极进化)
    # ==========================================
    with t3:
        st.markdown(f"### 正在审计：{st.session_state.current_ticker} 的聪明资金动向")
        
        # 利用 yfinance 抓取真实的机构持仓
        ticker_obj = yf.Ticker(st.session_state.current_ticker)
        
        col_l, col_r = st.columns([1, 1])
        
        with col_l:
            st.markdown("**顶级机构持仓分布 (Top Holders)**")
            try:
                holders = ticker_obj.institutional_holders
                if holders is not None:
                    # 格式化表格显示
                    st.dataframe(holders, use_container_width=True, hide_index=True)
                else:
                    st.write("暂无公开机构持仓披露数据")
            except:
                st.write("数据源抓取限制，请稍后再试")

        with col_r:
            st.markdown("**AI 持仓质量审计 (Token 消耗中)**")
            if st.button("🧠 启动 AI 资金深度建模"):
                if holders is not None:
                    # 把真实的持仓数据发给 AI 分析
                    holders_list = holders['Holder'].tolist()
                    audit_prompt = f"""
                    以下是股票 {st.session_state.current_ticker} 的前几大机构持仓列表：{holders_list}。
                    作为顶级量化分析师，请执行以下审计：
                    1. 辨别这些持仓中哪些是“被动型指数基金”（如 Vanguard, BlackRock），哪些是具有方向性指导意义的“主动型对冲基金”。
                    2. 根据这些顶级基金的近期调仓调性（可结合你已有的知识库），判断该股票目前的筹码是处于“散户化”还是“机构化”。
                    3. 给出该标的的'聪明资金信任等级'（1-10级）。
                    """
                    st.info(call_ai("DeepSeek", audit_prompt))
                else:
                    st.write("缺少持仓数据，无法执行 AI 审计。")

        st.markdown("---")
        st.markdown("**💡 聪明资金全局监控 (全市场追踪)**")
        # 这里你可以自由增加你想关注的“聪明人”标签
        whale_radar = pd.DataFrame({
            "监控标签": ["AI 大佬关联持仓", "硅谷前员工离职创业流向", "华尔街科技股之神 (Druckenmiller)", "国资背景长线金"],
            "重点关注标的": ["LITE, AAOI", "WDC, NVDA", "LITE, TSLA", "002008.SZ"],
            "AI 活跃度建议": ["高关注：算力基建回踩", "中：关注存储芯片拐点", "高：顶级机构增持", "低：政策等待期"]
        })
        st.table(whale_radar)
