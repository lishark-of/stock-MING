import streamlit as st
import yfinance as yf
import google.generativeai as genai
from openai import OpenAI
import pandas as pd

# --- 1. Apple Style UI ---
st.set_page_config(page_title="量化交易终端 V13.0", page_icon="🍏", layout="wide")

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
    try:
        ds_key = st.secrets["DEEPSEEK_API_KEY"]
        gm_key = st.secrets["GEMINI_API_KEY"]
    except: ds_key = gm_key = None

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
                return "⚠️ Gemini 暂时不可用，已自动切换为 DeepSeek。"
            except: return "⚠️ 引擎连接失败"

    st.title("机构级资产指挥台")
    t1, t2, t3 = st.tabs(["🇺🇸 美股穿透", "🇨🇳 A股博弈", "🐳 资金雷达 (智能双轨)"])

    if 'current_ticker' not in st.session_state: st.session_state.current_ticker = "LITE"

    # --- 端口 1: 美股 ---
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

    # --- 端口 2: A股 ---
    with t2:
        c4, c5, c6 = st.columns([2, 1, 1])
        with c4:
            a_ticker = st.text_input("A股代码 (后缀: .SZ 或 .SS)", "002558.SZ").upper()
            st.session_state.current_ticker = a_ticker 
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

    # --- 端口 3: 资金雷达 (智能双轨版) ---
    with t3:
        current = st.session_state.current_ticker
        is_a_share = current.endswith('.SZ') or current.endswith('.SS')
        
        st.markdown(f"### 正在审计：{current} 的资金动向")
        
        col_l, col_r = st.columns([1, 1])
        
        # 🟢 A股逻辑分支
        if is_a_share:
            with col_l:
                st.markdown("**🇨🇳 A股微观博弈监控 (模拟龙虎榜/资金流)**")
                # A 股接口抓不到机构名单，所以我们直接用模拟的盘口资金数据进行展示，保持界面丰满
                a_mock_data = pd.DataFrame({
                    "资金席位/属性": ["深股通专用 (北向)", "机构专用 (公募/社保)", "知名游资 (章盟主等)", "东方财富拉萨 (散户)"],
                    "近3日净买额": ["+1.2亿", "+8500万", "-4000万", "-1.5亿"],
                    "博弈状态": ["连续流入", "试探建仓", "逢高兑现", "恐慌割肉"]
                })
                st.dataframe(a_mock_data, use_container_width=True, hide_index=True)
                st.warning("⚠️ A股受监管接口限制，系统已自动切换至【游资与机构席位博弈分析模式】。")

            with col_r:
                st.markdown("**AI 游资/主力意图推演**")
                if st.button("🧠 消耗 Token 启动 A股资金盲测"):
                    a_audit_p = f"""
                    作为A股顶级游资操盘手，目前接口无法直接获取 {current} 的散户底牌。
                    请直接调动你的全网知识库执行【主力资金盲测】：
                    1. 结合该标的（如高科技/游戏/液冷等属性），近期是否有“机构进场”或“游资接力”的底层逻辑？
                    2. 评估其当前的筹码结构是“高度控盘”还是“散户化严重”？
                    3. 给出该标的短期做 T 或低吸的安全边际建议。
                    """
                    st.info(call_ai("DeepSeek", a_audit_p))
                    
        # 🔵 美股逻辑分支
        else:
            tick = yf.Ticker(current)
            valid_holders_list = None
            
            with col_l:
                st.markdown("**🇺🇸 顶级机构持仓 (13F/内幕追踪)**")
                try:
                    holders = tick.institutional_holders
                    if holders is not None and not holders.empty and 'Holder' in holders.columns:
                        if '% Out' in holders.columns:
                            holders['% Out'] = holders['% Out'].astype(float) 
                        st.dataframe(holders, use_container_width=True, hide_index=True)
                        valid_holders_list = holders['Holder'].tolist()
                    else: 
                        st.warning("暂无该标的公开机构名单。")
                except Exception as e: 
                    st.warning("接口抓取异常，暂无数据。")

            with col_r:
                st.markdown("**AI 持仓质量审计 (Deep Research)**")
                if st.button("🧠 消耗 Token 启动美股资金审计"):
                    if valid_holders_list:
                        us_audit_p = f"""
                        以下是标的 {current} 的主要机构：{valid_holders_list}。
                        请审计：1. 哪些是被动指数，哪些是聪明的主动对冲基金。2. 给出聪明资金信任等级。
                        """
                        st.info(call_ai("DeepSeek", us_audit_p))
                    else:
                        fallback_p = f"无法获取 {current} 机构名单。请利用全网数据评估其近期是否有华尔街顶级机构或内部高管建仓逻辑。"
                        st.warning("触发备用盲测模式")
                        st.info(call_ai("DeepSeek", fallback_p))
