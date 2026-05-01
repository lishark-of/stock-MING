import streamlit as st
import time

# --- 1. 页面基本设置 ---
st.set_page_config(page_title="双核交易指挥中心", page_icon="📈", layout="centered")

# --- 2. 权限管理系统 ---
# 初始化登录状态
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

def check_password():
    """验证账号密码"""
    # 这里设置你的专属账号和密码，你可以自行修改
    ADMIN_USER = "boss"
    ADMIN_PASS = "888888"
    
    if st.session_state["username"] == ADMIN_USER and st.session_state["password"] == ADMIN_PASS:
        st.session_state['logged_in'] = True
        st.success("身份验证成功，正在加载核心数据...")
        time.sleep(1)
        st.rerun()
    else:
        st.error("⚠️ 账号或密码错误，拒绝访问。")

def logout():
    """退出登录"""
    st.session_state['logged_in'] = False
    st.rerun()

# --- 3. 登录界面 ---
if not st.session_state['logged_in']:
    st.markdown("<h2 style='text-align: center; color: #E63946;'>🔒 私有化交易指挥中心</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center;'>仅限管理员访问</p>", unsafe_allow_html=True)
    
    st.text_input("管理员账号", key="username")
    st.text_input("安全密码", type="password", key="password")
    st.button("🔑 登录系统", on_click=check_password)

# --- 4. App 主界面 (登录后可见) ---
else:
    st.sidebar.button("退出系统", on_click=logout)
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📊 账户状态\n**当前模式:** 高级管理员\n**系统状态:** 实时监控中")

    st.title("⚡ 双核量化诊股终端 v3.0")
    
    # 核心输入区
    col1, col2 = st.columns(2)
    with col1:
        stock = st.selectbox("选择或输入自选标的", ["大族激光 (002008)", "巨人网络 (002558)", "英维克 (002837)", "Lumentum (LITE)", "其他标的"])
    with col2:
        mode = st.radio("切换交易端口", ["🔴 短线博弈 (情绪与资金)", "🔵 长线价值 (政策与估值)"])

    macro_event = st.selectbox("当前宏观/地缘因子", ["无重大事件", "科技制裁加码/出口受限", "AI算力资本开支超预期", "指数情绪冰点/恐慌杀跌"])

    st.markdown("---")

    # 动态诊断输出区
    if st.button("🚀 启动深度推演"):
        with st.spinner('正在穿透微观资金与量化模型...'):
            time.sleep(1.5) # 模拟计算延迟
            
            if mode == "🔴 短线博弈 (情绪与资金)":
                st.subheader(f"【短线博弈局】: {stock}")
                st.warning("⚠️ **风控雷达提示**：当前关注点为量化资金痕迹与短期情绪共振。")
                
                if "大族激光" in stock:
                    st.write("**资金面画像：** 机构锁仓与游资高频做 T 并存。")
                    st.write("**实战建议：** 遇急跌在关键支撑位左侧低吸，盘中受消息刺激拉升 3%-5% 果断抛出筹码，滚动做 T 摊低成本。")
                elif "英维克" in stock and "AI算力" in macro_event:
                    st.success("**情绪共振：** 液冷概念受外部算力资本开支催化，重点观察北向资金接力情况，主升浪切勿轻易下车。")
                
                if "冰点" in macro_event:
                    st.error("🚨 **大盘系统性风险警告：** 市场容错率极低，防范量化资金机械式融券砸盘，建议严控仓位至 2 成以下。")

            else:
                st.subheader(f"【长线价值港】: {stock}")
                st.info("💡 **深度投资提示**：当前关注点为产业周期、核心估值与大股东动向。")
                
                if "大族激光" in stock:
                    st.write("**基本面预期差：** 市场仍以果链估值，未完全计入半导体设备与先进封装潜力。")
                    st.write("**长线建议：** 估值处于高性价比区间，保留底仓，等待消费电子周期反转与半导体业务双击。")
                elif "LITE" in stock:
                    st.write("**价值模式追踪：** 前期已执行 2/5 仓位止盈，锁定 30% 利润。剩余底仓继续享受 AI 光模块产业红利。")
                    
                if "制裁" in macro_event:
                    st.warning("🌐 **宏观对冲：** 注意出口链短期承压，但长期加速国产替代逻辑。")