import streamlit as st
import yfinance as yf
import google.generativeai as genai
from openai import OpenAI
import pandas as pd
import time

# --- 1. Apple Style UI ---
st.set_page_config(page_title="量化交易终端 V14.0", page_icon="🍏", layout="wide")

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

    # ==========================================
    # 🆕 亮点 1：量化画风进度条组件
    # ==========================================
    def run_quant_progress():
        bar = st.progress(0)
        status_text = st.empty()
        steps = [
            "📡 正在接入数据源...", 
            "🔍 正在抓取机构与主力底层底牌...", 
            "🧮 正在注入蒙特卡洛模型推演价格极值...", 
            "⚡ 正在穿透筹码断层，生成最终作战策略..."
        ]
        for i in range(100):
            bar.progress(i + 1)
            if i % 25 == 0:
                status_text.markdown(f"<p class='status-text'>{steps[i//25]}</p>", unsafe_allow_html=True)
            time.sleep(0.015) # 进度条动画时间
        status_text.empty()
        bar.empty()

    # ==========================================
    # 🆕 亮点 2：流式打字机输出函数 (DeepSeek)
    # ==========================================
    def call_deepseek_stream(prompt):
        if not ds_key: return st.error("缺少 DeepSeek 密钥")
        try:
            client = OpenAI(api_key=ds_key, base_url="https://api.deepseek.com/v1")
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": f"【深度审计模式】{prompt}"}],
                stream=True # 开启流式输出
            )
            # 配合 Streamlit 的流式写入功能
            st.write_stream((chunk.choices[0].delta.content or "") for chunk in response)
        except Exception as e:
            st.error("DeepSeek 连接异常，请重试。")

    def call_gemini(prompt):
        try:
            genai.configure(api_key=gm_key)
            for m in ['gemini-1.5-flash', 'gemini-pro']:
                try: return genai.GenerativeModel(m).generate_content(prompt).text
                except: continue
            return "⚠️ Gemini 暂时不可用。"
        except: return "⚠️ 引擎连接失败"

    st.title("机构级资产指挥台")
    
    # ==========================================
    # 🆕 亮点 3：全局目标锁定 (取代各分页单独搜索)
    # ==========================================
    st.markdown("### 🎯 全局目标锁定")
    top_c1, top_c2, top_c3 = st.columns([2, 1, 2])
    with top_c1:
        # 输入框直接控制全局
        target = st.text_input("输入监控代码 (如 LITE, AAPL, 002008.SZ)", "LITE", label_visibility="collapsed").upper()
    with top_c2:
        try:
            p = round(yf.Ticker(target).history(period='1d')['Close'].iloc[0], 2)
            st.metric("卫星侦测价格", f"{p}")
        except: p = "N/A"; st.metric("卫星侦测价格", "--")
    with top_c3:
        global_engine = st.radio("全局算力调度", ["DeepSeek", "Gemini", "双擎验证"], horizontal=True, label_visibility="collapsed")
        
    st.markdown("---")

    t1, t2, t3 = st.tabs(["🇺🇸 美股深度研报", "🇨🇳 A股微观博弈", "🐳 全局聪明资金雷达"])

    # --- 端口 1: 美股 ---
    with t1:
        if st.button(f"🚀 启动 Deep Research：{target}", key="btn_us"):
            if st.session_state.user_role == "Admin":
                prompt = f"分析美股标的{target}，价{p}。结合AI算力物理瓶颈、价值错杀进行推演，给出阶梯式止盈与底仓管理建议。"
                run_quant_progress() # 触发量化进度条
                
                if global_engine in ["DeepSeek", "双擎验证"]: 
                    st.markdown("### 🔴 DeepSeek 深度推演流")
                    call_deepseek_stream(prompt) # 触发打字机输出
                    
                if global_engine in ["Gemini", "双擎验证"]: 
                    st.markdown(f"### 🔵 Gemini 宏观洞察\n{call_gemini(prompt)}")
            else: st.error("访客权限受限")

    # --- 端口 2: A股 ---
    with t2:
        if st.button(f"🚀 启动量化穿透：{target}", key="btn_a"):
            if st.session_state.user_role == "Admin":
                prompt_a = f"分析A股标的{target}，价{p}。分析筹码断层、主力/游资博弈痕迹、做T空间，并给出精确到小数点的止盈止损建议。"
                run_quant_progress()
                
                if global_engine in ["DeepSeek", "双擎验证"]: 
                    st.markdown("### 🔴 DeepSeek 量化推演流")
                    call_deepseek_stream(prompt_a)
                    
                if global_engine in ["Gemini", "双擎验证"]: 
                    st.markdown(f"### 🔵 Gemini 政策解读\n{call_gemini(prompt_a)}")
            else: st.error("访客权限受限")

    # --- 端口 3: 资金雷达 (自动跟随全局 target) ---
    with t3:
        is_a_share = target.endswith('.SZ') or target.endswith('.SS')
        st.markdown(f"### 正在审计：{target} 的资金动向")
        col_l, col_r = st.columns([1, 1])
        
        # 🟢 A股雷达逻辑
        if is_a_share:
            with col_l:
                st.markdown("**🇨🇳 A股微观博弈监控 (模拟席位)**")
                a_mock = pd.DataFrame({"资金席位": ["深股通专用", "机构专用", "知名游资", "东方财富拉萨"], "净买额": ["+1.2亿", "+8500万", "-4000万", "-1.5亿"], "状态": ["连续流入", "试探建仓", "逢高兑现", "恐慌割肉"]})
                st.dataframe(a_mock, use_container_width=True, hide_index=True)
            with col_r:
                st.markdown("**AI 主力意图推演**")
                if st.button("🧠 消耗 Token 启动 A股资金盲测", key="btn_t3_a"):
                    run_quant_progress()
                    a_audit_p = f"作为顶级游资，直接盲测 {target} 的主力资金潜伏逻辑、筹码控盘度及安全边际。"
                    st.markdown("### 🔴 DeepSeek 资金推演")
                    call_deepseek_stream(a_audit_p)
                    
        # 🔵 美股雷达逻辑
        else:
            tick = yf.Ticker(target)
            valid_holders = None
            with col_l:
                st.markdown("**🇺🇸 顶级机构持仓 (点击排序)**")
                try:
                    holders = tick.institutional_holders
                    if holders is not None and not holders.empty and 'Holder' in holders.columns:
                        if '% Out' in holders.columns: holders['% Out'] = holders['% Out'].astype(float) 
                        st.dataframe(holders, use_container_width=True, hide_index=True)
                        valid_holders = holders['Holder'].tolist()
                    else: st.warning("暂无公开名单。")
                except: st.warning("抓取异常。")

            with col_r:
                st.markdown("**AI 持仓质量审计**")
                if st.button("🧠 消耗 Token 启动美股资金审计", key="btn_t3_us"):
                    run_quant_progress()
                    st.markdown("### 🔴 DeepSeek 审计流")
                    if valid_holders:
                        call_deepseek_stream(f"审计 {target} 的主要机构：{valid_holders}。区分被动指数与主动基金，给出信任等级。")
                    else:
                        call_deepseek_stream(f"无法获取 {target} 机构名单。请利用全网数据评估其顶级机构或高管建仓逻辑。")
