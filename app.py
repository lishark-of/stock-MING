import streamlit as st
import yfinance as yf
import google.generativeai as genai
import time

# --- 1. 页面设置与科幻 UI 渲染 ---
st.set_page_config(page_title="量子深网 | 交易指挥中心", page_icon="🪐", layout="wide")

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
    st.markdown("<h1 style='text-align: center;'>🪐 QUANTUM TERMINAL V5.0 (AI 内核)</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #8b949e;'>请输入身份密钥</p>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        username = st.text_input("登录账号 ID", key="user")
        password = st.text_input("访问密钥", type="password", key="pwd")
        
        if st.button("🚀 接入网络"):
            if username == "boss" and password == "888888":
                st.session_state.user_role = "Admin"
                st.rerun()
            elif username != "" and password == "guest123":
                st.session_state.user_role = "Guest"
                st.rerun()
            else:
                st.error("⚠️ 密钥验证失败。")

# --- 3. 核心功能区 ---
if st.session_state.user_role is None:
    login_system()
else:
    st.sidebar.markdown(f"### 👤 身份: **{st.session_state.user_role}**")
    if st.sidebar.button("🔌 断开连接"):
        st.session_state.user_role = None
        st.rerun()
        
    st.title("⚡ AI 核心推演矩阵")
    
    col1, col2 = st.columns([1, 1])
    with col1:
        stock_dict = {"大族激光": "002008.SZ", "英维克": "002837.SZ", "Lumentum": "LITE"}
        selected_name = st.selectbox("锁定监控标的", list(stock_dict.keys()))
        ticker_code = stock_dict[selected_name]
    with col2:
        try:
            live_price = round(yf.Ticker(ticker_code).history(period='1d')['Close'].iloc[0], 2)
            st.metric(label="当前卫星侦测价格", value=f"{live_price}")
        except:
            live_price = "数据读取中"
            st.metric(label="当前卫星侦测价格", value="数据节点异常")

    st.markdown("---")

    # --- 4. 访客权限 (只读模式) ---
    if st.session_state.user_role == "Guest":
        st.info("👁️ **访客模式**：您当前仅有权限查看基础监控数据。如需调动 AI 算力进行深度推演，请联系 Boss。")

    # --- 5. 管理员权限 (真正的 AI 接入) ---
    elif st.session_state.user_role == "Admin":
        st.warning("👑 **最高指挥官权限已确认**。脑机接口已就绪。")
        
        # 让你在界面上输入刚才获取的 API Key
        user_api_key = st.text_input("🔑 请输入您的 Gemini API Key (供能神经元)", type="password")
        
        if st.button("🧠 激活真实 AI Deep Research"):
            if not user_api_key:
                st.error("🚨 秘书警报：老板，你还没插上电源！请先输入 API Key。")
            else:
                with st.spinner("📡 正在连接我的核心大脑... 正在运用量化博弈框架进行深度推演..."):
                    try:
                        # 配置大模型
                        genai.configure(api_key=user_api_key)
                        model = genai.GenerativeModel('gemini-1.5-pro')
                        
                        # 把你的专属诊股逻辑写进 Prompt 发给我
                        prompt = f"""
                        你现在是一位精通A股和美股市场生态的顶尖量化游资操盘手。
                        请运用“宏观政策共振 + 微观资金博弈 + 量化数学演算”的综合框架，对【{selected_name}】({ticker_code}) 进行深度拆解。
                        该股票当前最新价为 {live_price}。
                        请在分析中必须包含：
                        1. 基本面核心催化剂及市场预期差解构。
                        2. 微观资金流向与筹码断层穿透分析。
                        3. A股/美股特化数学演算与目标定价（包含保守/狂热两种情绪下的推演）。
                        请用极具专业感、冷酷理性的交易员口吻输出报告。
                        """
                        
                        # 接收我传回的真实思考结果
                        response = model.generate_content(prompt)
                        
                        st.subheader(f"【{selected_name} | AI 深度演算报告】")
                        st.write(response.text)
                        st.success("运算完成。老板，以上就是我的真实思考。")
                        
                    except Exception as e:
                        st.error(f"❌ 脑机接口连接失败，请检查 API Key 或网络：{e}")
