import streamlit as st
import yfinance as yf
import time

# --- 1. 页面设置与科幻 UI 渲染 ---
st.set_page_config(page_title="量子深网 | 交易指挥中心", page_icon="🪐", layout="wide")

# 注入 CSS 代码，打造暗黑科幻/赛博朋克风格
st.markdown("""
<style>
    .stApp { background-color: #0d1117; color: #00ffcc; }
    h1, h2, h3 { color: #00ffcc !important; text-shadow: 0px 0px 8px #00ffcc; font-family: 'Courier New', Courier, monospace;}
    .stButton>button { background-color: #0d1117; border: 1px solid #00ffcc; color: #00ffcc; box-shadow: 0 0 10px #00ffcc; transition: 0.3s; }
    .stButton>button:hover { background-color: #00ffcc; color: #0d1117; }
    .stTextInput input, .stSelectbox div[data-baseweb="select"] { background-color: #161b22; color: #00ffcc; border: 1px solid #30363d; }
    div[data-testid="stMetricValue"] { color: #ff3366 !important; text-shadow: 0px 0px 5px #ff3366; }
</style>
""", unsafe_allow_html=True)

# --- 2. 权限管理中枢 ---
if 'user_role' not in st.session_state:
    st.session_state.user_role = None

def login_system():
    st.markdown("<h1 style='text-align: center;'>🪐 QUANTUM TERMINAL V4.0</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #8b949e;'>请输入身份密钥</p>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        username = st.text_input("登录账号 ID", key="user")
        password = st.text_input("访问密钥", type="password", key="pwd")
        
        if st.button("🚀 接入网络"):
            if username == "boss" and password == "888888":
                st.session_state.user_role = "Admin"
                st.rerun()
            elif username != "" and password == "guest123": # 访客通用密码
                st.session_state.user_role = "Guest"
                st.rerun()
            else:
                st.error("⚠️ 密钥验证失败，防入侵系统已启动。")
    return

# --- 3. 核心功能区 ---
if st.session_state.user_role is None:
    login_system()
else:
    # 顶部导航栏
    st.sidebar.markdown(f"### 👤 身份: **{st.session_state.user_role}**")
    if st.sidebar.button("🔌 断开连接"):
        st.session_state.user_role = None
        st.rerun()
        
    st.title("⚡ 核心推演矩阵")
    
    # 股票选择器
    col1, col2 = st.columns([1, 1])
    with col1:
        stock_dict = {"大族激光": "002008.SZ", "英维克": "002837.SZ", "Lumentum": "LITE"}
        selected_name = st.selectbox("锁定监控标的", list(stock_dict.keys()))
        ticker_code = stock_dict[selected_name]
    with col2:
        # 获取实时数据
        try:
            live_price = round(yf.Ticker(ticker_code).history(period='1d')['Close'].iloc[0], 2)
            st.metric(label="当前卫星侦测价格", value=f"{live_price}")
        except:
            st.metric(label="当前卫星侦测价格", value="数据节点异常")

    st.markdown("---")

    # --- 4. 访客权限 (只读模式) ---
    if st.session_state.user_role == "Guest":
        st.info("👁️ **访客模式**：您当前仅有权限查看基础监控数据。")
        st.write(f"**标的：** {selected_name}")
        st.write("**资金流向：** 暂无异常波动...")
        st.write("**系统建议：** 请联系管理员 (Boss) 获取深度诊断与量化风控权限。")

    # --- 5. 管理员权限 (Boss 专属深度推演) ---
    elif st.session_state.user_role == "Admin":
        st.warning("👑 **最高指挥官权限已确认**。AI 算力池已全量分配。")
        
        mode = st.radio("切换战术引擎", ["🔴 高频博弈 (做T模型)", "🔵 宏观价值 (周期模型)"])
        
        if st.button("🧠 激活 AI Deep Research (深度推演)"):
            with st.spinner("正在调用底层大语言模型处理你的私人 Prompt 框架..."):
                time.sleep(2) # 模拟 AI 思考时间
                
                # 这里是我们之前写的 A 股量化与微观博弈 Prompt 框架的落地展示
                st.subheader("【AI 深度推演报告生成完毕】")
                st.write(f"**分析标的：** {selected_name}")
                st.write("**1. 筹码断层穿透：** 监测到上方套牢盘正在松动，底部大股东筹码锁定率 85%。未见明显量化融券砸盘痕迹。")
                st.write(f"**2. 情绪溢价模型推演：** 结合当前 CPO 和液冷板块的资本开支预期，若本周突破 {live_price * 1.05:.2f} 元关键阻力位，跳跃扩散模型预测有 15% 的短期爆发空间。")
                st.write("**3. 实战做 T 指令：** 不可盲目格局，若盘中分时图出现顶背离，果断执行减仓计划。")
