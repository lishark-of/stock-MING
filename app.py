import streamlit as st
import yfinance as yf
import google.generativeai as genai
from openai import OpenAI
import time

# --- 1. 页面设置 ---
st.set_page_config(page_title="双核交易终端", page_icon="🍏", layout="centered")

# --- 2. 苹果风 (Apple Style) UI 渲染 ---
st.markdown("""
<style>
    /* 引入苹果系字体并在全局应用高级灰底色 */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');
    .stApp { 
        background-color: #F5F5F7; 
        color: #1D1D1F; 
        font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }
    
    /* 标题与文字颜色极其克制 */
    h1, h2, h3 { color: #1D1D1F !important; font-weight: 600; letter-spacing: -0.02em; }
    p { color: #515154; }
    
    /* 苹果标志性的胶囊按钮 (Pill-shaped Button) */
    .stButton>button { 
        background-color: #0071E3; 
        color: white; 
        border-radius: 980px; 
        border: none; 
        padding: 8px 24px; 
        font-weight: 500; 
        box-shadow: 0 4px 14px rgba(0, 113, 227, 0.2);
        transition: all 0.2s ease-in-out; 
    }
    .stButton>button:hover { background-color: #0077ED; transform: scale(1.02); box-shadow: 0 6px 20px rgba(0, 113, 227, 0.3); color: white;}
    
    /* 输入框与选择器的圆角和毛玻璃质感 */
    .stTextInput input, .stSelectbox div[data-baseweb="select"] { 
        border-radius: 12px; 
        border: 1px solid #D2D2D7; 
        background-color: rgba(255, 255, 255, 0.8); 
        color: #1D1D1F; 
        backdrop-filter: blur(10px);
    }
    
    /* 大号数据展示的高级感 */
    div[data-testid="stMetricValue"] { color: #1D1D1F !important; font-weight: 600; font-size: 2.2rem; letter-spacing: -0.03em;}
    div[data-testid="stMetricLabel"] { color: #86868B !important; font-size: 0.9rem;}
</style>
""", unsafe_allow_html=True)

# --- 3. 极简权限验证 ---
if 'user_role' not in st.session_state:
    st.session_state.user_role = None

if st.session_state.user_role is None:
    st.markdown("<h1 style='text-align: center; margin-top: 10vh;'>Terminal</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; margin-bottom: 40px;'>输入您的访问凭证</p>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        password = st.text_input("", type="password", placeholder="Password", label_visibility="collapsed")
        st.write("") # 占位
        if st.button("登录", use_container_width=True):
            if password == "888888":  # Boss 密码极简化
                st.session_state.user_role = "Admin"
                st.rerun()
            elif password == "guest":
                st.session_state.user_role = "Guest"
                st.rerun()
            else:
                st.error("验证失败")
else:
    # --- 4. 主界面 (极简无框设计) ---
    colA, colB = st.columns([3, 1])
    with colA:
        st.title("诊股终端")
    with colB:
        st.write("")
        if st.button("退出"):
            st.session_state.user_role = None
            st.rerun()
            
    st.markdown("---")
    
    col1, col2 = st.columns([1, 1])
    with col1:
        stock_dict = {"大族激光": "002008.SZ", "英维克": "002837.SZ", "巨人网络": "002558.SZ", "Lumentum": "LITE"}
        selected_name = st.selectbox("监控标的", list(stock_dict.keys()), label_visibility="collapsed")
        ticker_code = stock_dict[selected_name]
    with col2:
        try:
            live_price = round(yf.Ticker(ticker_code).history(period='1d')['Close'].iloc[0], 2)
            st.metric(label="当前实时报价", value=f"¥ {live_price}")
        except:
            live_price = "获取中"
            st.metric(label="当前实时报价", value="--")

    if st.session_state.user_role == "Guest":
        st.info("访客模式：仅提供基础行情概览。")
        
    elif st.session_state.user_role == "Admin":
        st.write("")
        engine_choice = st.radio("AI 运算集群", ["Gemini", "DeepSeek", "双擎验证"], horizontal=True)
        
        # 按钮完全剥离了原来复杂的输入框
        if st.button("开始深度推演", use_container_width=True):
            prompt = f"以顶级量化游资操盘手身份，用微观资金博弈+量化演算框架拆解【{selected_name}】({ticker_code})，当前价 {live_price}。需包含预期差、筹码断层与极端推演。"
            
            # --- 自动从保险箱读取钥匙，如果没配会报错提示 ---
            try:
                gemini_key = st.secrets["GEMINI_API_KEY"]
            except:
                gemini_key = None
            try:
                deepseek_key = st.secrets["DEEPSEEK_API_KEY"]
            except:
                deepseek_key = None

            # --- Gemini 引擎 ---
            if engine_choice in ["Gemini", "双擎验证"]:
                if not gemini_key:
                    st.error("未在 Streamlit Secrets 中配置 GEMINI_API_KEY")
                else:
                    with st.spinner("Gemini 正在分析宏观基本面..."):
                        genai.configure(api_key=gemini_key)
                        model = genai.GenerativeModel('gemini-1.5-pro')
                        st.markdown("### Gemini 洞察")
                        st.write(model.generate_content(prompt).text)

            # --- DeepSeek 引擎 ---
            if engine_choice in ["DeepSeek", "双擎验证"]:
                if not deepseek_key:
                    st.error("未在 Streamlit Secrets 中配置 DEEPSEEK_API_KEY")
                else:
                    with st.spinner("DeepSeek 正在执行量化逻辑推演..."):
                        client = OpenAI(api_key=deepseek_key, base_url="https://api.deepseek.com/v1")
                        ds_response = client.chat.completions.create(
                            model="deepseek-chat",
                            messages=[{"role": "user", "content": prompt}]
                        ).choices[0].message.content
                        st.markdown("### DeepSeek 演算")
                        st.write(ds_response)
