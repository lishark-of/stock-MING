import streamlit as st
import yfinance as yf
import google.generativeai as genai
from openai import OpenAI
import pandas as pd
import time

# --- 1. 页面设置 ---
st.set_page_config(page_title="量化交易终端", page_icon="🍏", layout="wide")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');
    .stApp { background-color: #F5F5F7; color: #1D1D1F; font-family: -apple-system, BlinkMacSystemFont, sans-serif; }
    h1, h2, h3 { color: #1D1D1F !important; font-weight: 600; letter-spacing: -0.02em; }
    .stButton>button { background-color: #0071E3; color: white; border-radius: 980px; border: none; padding: 6px 20px; font-weight: 500; box-shadow: 0 4px 14px rgba(0, 113, 227, 0.2); }
    .stButton>button:hover { background-color: #0077ED; transform: scale(1.02); color: white;}
    .stTextInput input { border-radius: 12px; border: 1px solid #D2D2D7; }
</style>
""", unsafe_allow_html=True)

# --- 2. 权限验证 ---
if 'user_role' not in st.session_state:
    st.session_state.user_role = None

if st.session_state.user_role is None:
    st.markdown("<h1 style='text-align: center; margin-top: 10vh;'>Terminal</h1>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        password = st.text_input("", type="password", placeholder="Password", label_visibility="collapsed")
        if st.button("登录", use_container_width=True):
            if password == "888888":
                st.session_state.user_role = "Admin"
                st.rerun()
            elif password == "guest":
                st.session_state.user_role = "Guest"
                st.rerun()
            else:
                st.error("验证失败")
else:
    # --- 3. 基础设置与 API 密钥 ---
    try:
        deepseek_key = st.secrets["DEEPSEEK_API_KEY"]
    except:
        deepseek_key = None
    try:
        gemini_key = st.secrets["GEMINI_API_KEY"]
    except:
        gemini_key = None

    colA, colB = st.columns([5, 1])
    with colA:
        st.title("机构级资产指挥台")
    with colB:
        if st.button("退出系统"):
            st.session_state.user_role = None
            st.rerun()
            
    st.markdown("---")
    
    tab_us, tab_a, tab_whale = st.tabs(["🇺🇸 美股", "🇨🇳 A股", "🐳 资金追踪"])
    
    # 统一推演函数，增加容错和备用模型列表
    def run_inference(engine, prompt):
        if engine == "Gemini":
            if not gemini_key:
                return "❌ 未配置 GEMINI_API_KEY"
            with st.spinner("Gemini 正在分析..."):
                try:
                    genai.configure(api_key=gemini_key)
                    # 尝试备用模型列表
                    for model_name in ['gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-pro']:
                        try:
                            model = genai.GenerativeModel(model_name)
                            response = model.generate_content(prompt)
                            return f"🔵 **Gemini ({model_name}) 洞察：**\n\n" + response.text
                        except Exception as inner_e:
                            continue
                    return "❌ Gemini 所有可用模型尝试失败。可能是服务器地理位置受限，建议检查 Streamlit Cloud 部署区域。"
                except Exception as e:
                    return f"❌ Gemini 连接失败: {str(e)}"
        
        elif engine == "DeepSeek":
            if not deepseek_key:
                return "❌ 未配置 DEEPSEEK_API_KEY"
            with st.spinner("DeepSeek 正在演算..."):
                try:
                    client = OpenAI(api_key=deepseek_key, base_url="https://api.deepseek.com/v1")
                    response = client.chat.completions.create(
                        model="deepseek-chat",
                        messages=[{"role": "user", "content": prompt}]
                    ).choices[0].message.content
                    return "🔴 **DeepSeek 深度逻辑：**\n\n" + response
                except Exception as e:
                    return f"❌ DeepSeek 连接失败: {str(e)}"

    # --- 模块：美股 ---
    with tab_us:
        col1, col2, col3 = st.columns([2, 1, 2])
        with col1:
            us_ticker = st.text_input("美股代码", "LITE").upper()
        with col2:
            try:
                price = round(yf.Ticker(us_ticker).history(period='1d')['Close'].iloc[0], 2)
                st.metric(label="USD", value=f"$ {price}")
            except:
                price = "N/A"
        with col3:
            eng_us = st.radio("算力选择", ["DeepSeek", "Gemini", "双擎"], horizontal=True, key="eng_us")
        
        if st.button(f"启动推演：{us_ticker}"):
            if st.session_state.user_role == "Admin":
                p = f"以顶级经理身份分析{us_ticker}，当前价{price}。需含：护城河、预期差、盈利建议与止损线。"
                if eng_us in ["DeepSeek", "双擎"]:
                    st.markdown(run_inference("DeepSeek", p))
                if eng_us in ["Gemini", "双擎"]:
                    st.markdown(run_inference("Gemini", p))
            else:
                st.error("权限不足")

    # --- 模块：A股 ---
    with tab_a:
        col4, col5, col6 = st.columns([2, 1, 2])
        with col4:
            a_ticker = st.text_input("A股代码 (需加后缀)", "002008.SZ").upper()
        with col5:
            try:
                price_a = round(yf.Ticker(a_ticker).history(period='1d')['Close'].iloc[0], 2)
                st.metric(label="CNY", value=f"¥ {price_a}")
            except:
                price_a = "N/A"
        with col6:
            eng_a = st.radio("算力选择 ", ["DeepSeek", "Gemini", "双擎"], horizontal=True, key="eng_a")

        if st.button(f"启动推演：{a_ticker}"):
            if st.session_state.user_role == "Admin":
                p_a = f"以量化游资身份分析{a_ticker}，当前价{price_a}。需含：筹码断层、盈利建议、做T策略与止损线。"
                if eng_a in ["DeepSeek", "双擎"]:
                    st.markdown(run_inference("DeepSeek", p_a))
                if eng_a in ["Gemini", "双擎"]:
                    st.markdown(run_inference("Gemini", p_a))

    # --- 模块：追踪 ---
    with tab_whale:
        mock_data = pd.DataFrame({
            "机构名称": ["Stanley Druckenmiller", "NVIDIA 高管", "Renaissance Tech"],
            "披露类型": ["13F", "Form 4", "13F"],
            "动作标的": ["AAOI, WDC", "NVDA", "LITE"],
            "信号": ["强力看多", "减持预警", "量化买入"]
        })
        st.dataframe(mock_data, use_container_width=True, hide_index=True)
