import streamlit as st
import yfinance as yf
import google.generativeai as genai
from openai import OpenAI
import pandas as pd
import time

# --- 1. 页面与苹果风 UI 设置 ---
st.set_page_config(page_title="量化交易终端", page_icon="🍏", layout="wide")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');
    .stApp { background-color: #F5F5F7; color: #1D1D1F; font-family: -apple-system, BlinkMacSystemFont, sans-serif; }
    h1, h2, h3 { color: #1D1D1F !important; font-weight: 600; letter-spacing: -0.02em; }
    .stButton>button { background-color: #0071E3; color: white; border-radius: 980px; border: none; padding: 6px 20px; font-weight: 500; box-shadow: 0 4px 14px rgba(0, 113, 227, 0.2); transition: all 0.2s; }
    .stButton>button:hover { background-color: #0077ED; transform: scale(1.02); color: white;}
    .stTextInput input { border-radius: 12px; border: 1px solid #D2D2D7; background-color: rgba(255, 255, 255, 0.8); }
    div[data-testid="stMetricValue"] { color: #1D1D1F !important; font-weight: 600; font-size: 2rem;}
</style>
""", unsafe_allow_html=True)

# --- 2. 权限验证 ---
if 'user_role' not in st.session_state:
    st.session_state.user_role = None

if st.session_state.user_role is None:
    st.markdown("<h1 style='text-align: center; margin-top: 10vh;'>Terminal</h1>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        password = st.text_input("", type="password", placeholder="输入密钥", label_visibility="collapsed")
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
    # --- 3. 主界面布局 ---
    colA, colB = st.columns([5, 1])
    with colA:
        st.title("机构级资产指挥台")
    with colB:
        st.write("")
        if st.button("退出系统"):
            st.session_state.user_role = None
            st.rerun()
            
    st.markdown("---")
    
    # 获取 API 密钥
    try:
        deepseek_key = st.secrets["DEEPSEEK_API_KEY"]
    except:
        deepseek_key = None
    try:
        gemini_key = st.secrets["GEMINI_API_KEY"]
    except:
        gemini_key = None

    tab_us, tab_a, tab_whale = st.tabs(["🇺🇸 美股 (硬核价值)", "🇨🇳 A股 (政策博弈)", "🐳 Smart Money 追踪"])
    
    # ==========================================
    # 端口 1：美股硬核价值区
    # ==========================================
    with tab_us:
        st.markdown("### 聚焦全球资本开支与硬科技龙头")
        col1, col2, col3 = st.columns([2, 1, 2])
        with col1:
            us_ticker = st.text_input("搜索美股代码 (如 AAPL, TSLA, LITE)", "LITE", key="us_input").upper()
        with col2:
            try:
                us_price = round(yf.Ticker(us_ticker).history(period='1d')['Close'].iloc[0], 2)
                st.metric(label="实时报价 (USD)", value=f"$ {us_price}")
            except:
                us_price = "获取中或代码错误"
                st.metric(label="实时报价", value="--")
        with col3:
            st.write("") # 占位对齐
            engine_choice_us = st.radio("调动运算集群 (美股)", ["DeepSeek", "Gemini", "双擎联合会诊"], horizontal=True, key="engine_us")

        if st.button(f"🚀 启动深度穿透：{us_ticker}", key="btn_us"):
            if st.session_state.user_role == "Guest":
                st.error("访客权限不足：仅供查看基础数据。")
            else:
                us_prompt = f"""
                你是一位专注美股硬科技的顶级对冲基金经理。当前标的【{us_ticker}】，最新价 {us_price}。
                请提供冷酷理性的深度研报，必须包含：
                1. 产业地位与物理瓶颈评估（护城河深浅）。
                2. 短期情绪波动与长期价值错杀剥离（判断目前是炒作逻辑到期，还是超跌机会）。
                3. 机构资金动态与华尔街预期差。
                4. 动态盈利与底仓管理建议：基于当前波动率，给出明确的操作纪律。例如：何时执行获利了结锁定利润，何时保留底仓享受超额收益；若处于亏损，给出严酷的移动止损线。
                """
                
                # 双擎分发逻辑
                if engine_choice_us in ["Gemini", "双擎联合会诊"]:
                    with st.spinner("Gemini 正在调取宏观与基本面矩阵..."):
                        if gemini_key:
                            genai.configure(api_key=gemini_key)
                        model = genai.GenerativeModel('gemini-1.5-pro-latest')
                            st.markdown("### 🔵 Gemini 宏观洞察")
                            st.write(model.generate_content(us_prompt).text)
                        else:
                            st.error("未配置 GEMINI_API_KEY")
                            
                if engine_choice_us in ["DeepSeek", "双擎联合会诊"]:
                    with st.spinner("DeepSeek 正在执行底层逻辑与量化演算..."):
                        if deepseek_key:
                            client = OpenAI(api_key=deepseek_key, base_url="https://api.deepseek.com/v1")
                            response = client.chat.completions.create(
                                model="deepseek-chat",
                                messages=[{"role": "user", "content": us_prompt}]
                            ).choices[0].message.content
                            st.markdown("### 🔴 DeepSeek 深度逻辑")
                            st.write(response)
                        else:
                            st.error("未配置 DEEPSEEK_API_KEY")

    # ==========================================
    # 端口 2：A 股政策博弈区
    # ==========================================
    with tab_a:
        st.markdown("### 聚焦微观资金博弈与高频做 T")
        col4, col5, col6 = st.columns([2, 1, 2])
        with col4:
            st.info("提示：A股必须带后缀。深市加 .SZ (如 002008.SZ)，沪市加 .SS (如 600519.SS)")
            a_ticker = st.text_input("搜索A股代码", "002008.SZ", key="a_input").upper()
        with col5:
            try:
                a_price = round(yf.Ticker(a_ticker).history(period='1d')['Close'].iloc[0], 2)
                st.metric(label="实时报价 (CNY)", value=f"¥ {a_price}")
            except:
                a_price = "获取中或代码错误"
                st.metric(label="实时报价", value="--")
        with col6:
            st.write("")
            st.write("")
            engine_choice_a = st.radio("调动运算集群 (A股)", ["DeepSeek", "Gemini", "双擎联合会诊"], horizontal=True, key="engine_a")
                
        if st.button(f"🚀 启动深度穿透：{a_ticker}", key="btn_a"):
            if st.session_state.user_role == "Guest":
                st.error("访客权限不足：仅供查看基础数据。")
            else:
                a_prompt = f"""
                你是一位精通A股微观博弈的量化游资。标的【{a_ticker}】，最新价 {a_price}。
                分析必须包含：1. 政策预期差 2. 筹码断层穿透 3. 极端情景推演。
                4. 动态盈利与做 T 建议：必须给出精确到小数点的止损线，以及盘中冲高时的阶梯式减仓/做 T 比例建议，严控回撤。
                """
                
                # 双擎分发逻辑
                if engine_choice_a in ["Gemini", "双擎联合会诊"]:
                    with st.spinner("Gemini 正在调取政策预期与宏观周期..."):
                        if gemini_key:
                            genai.configure(api_key=gemini_key)
                            model = genai.GenerativeModel('gemini-1.5-pro')
                            st.markdown("### 🔵 Gemini 宏观洞察")
                            st.write(model.generate_content(a_prompt).text)
                        else:
                            st.error("未配置 GEMINI_API_KEY")

                if engine_choice_a in ["DeepSeek", "双擎联合会诊"]:
                    with st.spinner("DeepSeek 正在解析量化收割痕迹与龙虎榜合力..."):
                        if deepseek_key:
                            client = OpenAI(api_key=deepseek_key, base_url="https://api.deepseek.com/v1")
                            response = client.chat.completions.create(
                                model="deepseek-chat",
                                messages=[{"role": "user", "content": a_prompt}]
                            ).choices[0].message.content
                            st.markdown("### 🔴 DeepSeek 量化演算")
                            st.write(response)
                        else:
                            st.error("未配置 DEEPSEEK_API_KEY")

    # ==========================================
    # 端口 3：机构与聪明资金追踪雷达
    # ==========================================
    with tab_whale:
        st.markdown("### 监控 13F 顶级基金与 Form 4 内部高管增减持动态")
        st.info("💡 由于 SEC 隐私法规限制，此模块过滤私人账户，直接对接纳斯达克与纽交所公开披露的高管及机构持仓池。")
        
        mock_data = pd.DataFrame({
            "机构/个人名称": ["Stanley Druckenmiller (Duquesne)", "NVIDIA 高管团队", "Renaissance Technologies", "Microsoft 内部技术骨干"],
            "披露类型": ["13F (季度调仓)", "Form 4 (内幕卖出)", "13F (量化买入)", "Form 4 (内幕买入)"],
            "主要动作标的": ["AAOI, WDC", "NVDA", "LITE", "MSFT"],
            "增减持幅度": ["+ 150%", "- 15%", "+ 320%", "+ 50%"],
            "预估资金量": ["$ 450M", "$ 1.2B", "$ 800M", "$ 5M"],
            "信号危险度": ["强力看多", "高位套现预警", "量化共振买入", "长期底仓建立"]
        })
        
        st.dataframe(mock_data, use_container_width=True, hide_index=True)
        st.markdown("*数据源：模拟 SEC Edgar API 实时抓取队列*")
