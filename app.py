import streamlit as st
import yfinance as yf
from openai import OpenAI
import datetime
import json
import os
import time

# --- 1. Apple Style UI ---
st.set_page_config(page_title="量化交易终端 V16.0", page_icon="🍏", layout="wide")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');
    .stApp { background-color: #F5F5F7; color: #1D1D1F; font-family: -apple-system, sans-serif; }
    .stButton>button { background-color: #1D1D1F; color: white; border-radius: 8px; border: none; width: 100%; font-weight: 500; transition: 0.2s; }
    .stButton>button:hover { background-color: #434343; color: white; }
    .stMetric { background-color: white; padding: 15px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.03); border: 1px solid #E5E5EA; }
    .risk-alert { background-color: #FFF0F0; padding: 15px; border-radius: 8px; border-left: 4px solid #FF3B30; margin-bottom: 10px; color: #FF3B30; font-weight: 600;}
</style>
""", unsafe_allow_html=True)

# --- 2. 策略外脑初始化 ---
KNOWLEDGE_FILE = "strategy_knowledge.json"
if not os.path.exists(KNOWLEDGE_FILE):
    with open(KNOWLEDGE_FILE, 'w', encoding='utf-8') as f:
        json.dump({"reflections": []}, f)

def save_lesson(lesson):
    with open(KNOWLEDGE_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    data["reflections"].append(lesson)
    with open(KNOWLEDGE_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# --- 3. 密钥与基础设置 ---
try:
    ds_key = st.secrets["DEEPSEEK_API_KEY"]
except:
    ds_key = None

def call_deepseek_stream(prompt, system_role="作为顶级量化基金经理。"):
    if not ds_key: return st.error("缺少 DeepSeek 密钥")
    try:
        client = OpenAI(api_key=ds_key, base_url="https://api.deepseek.com/v1")
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "system", "content": system_role}, {"role": "user", "content": prompt}],
            stream=True
        )
        st.write_stream((chunk.choices[0].delta.content or "") for chunk in response)
    except Exception as e:
        st.error(f"连接异常: {e}")

st.title("机构级资产指挥台 - 纪元版")
st.markdown("### 🎯 全局目标锁定")
top_c1, top_c2 = st.columns([3, 1])
with top_c1: 
    target = st.text_input("输入监控代码 (如 LITE, POET, 600481.SS)", "LITE", label_visibility="collapsed").upper()
with top_c2:
    try:
        p = round(yf.Ticker(target).history(period='1d')['Close'].iloc[0], 2)
        st.metric("卫星侦测价格", f"{p}")
    except: 
        p = "N/A"
        st.metric("卫星侦测价格", "--")

st.markdown("---")

tab_risk, tab_rl, tab_main = st.tabs(["🛡️ 天眼风控 (防雷)", "⏳ 炼丹炉 (强化学习)", "🇺🇸/🇨🇳 常规量化穿透"])

# ==========================================
# 模块 1：天眼风控 (合规与信息泄露排雷)
# ==========================================
with tab_risk:
    st.markdown(f"### 🛡️ 极高权限合规审计：{target}")
    st.info("消耗 Token 扫描内幕交易、消息抢跑、监管问询等治理风险，防范类似双良/POET的暴雷。")
    
    if st.button("🚨 启动全网风控雷达", key="btn_risk"):
        with st.spinner("正在扫描监管函件与舆情异动..."):
            try:
                # 抓取近期新闻标题作为情报源 
                news_data = yf.Ticker(target).news
                headlines = [n['title'] for n in news_data][:5] if news_data else "无公开实时新闻"
                
                risk_prompt = f"""
                你现在是 SEC 和中国证监会的顶级稽查员。标的：{target}。
                最新接口抓取到的舆情线索：{headlines}。
                请调动全网知识库，排查：
                1. 是否存在‘公告前股价已提前异动’的内幕泄露特征？
                2. 是否收到过监管关注函或遭到知名机构做空？
                3. 若存在类似双良或POET的信息违规风险，请在开头用【一票否决】做出严厉警告。
                """
                st.markdown("<div class='risk-alert'>正在执行深度排雷协议...</div>", unsafe_allow_html=True)
                call_deepseek_stream(risk_prompt, system_role="作为无情的金融监管稽查机器。")
            except Exception as e:
                st.error("数据抓取受限，建议手动补充舆情。")

# ==========================================
# 模块 2：炼丹炉 (历史回测与自我进化)
# ==========================================
with tab_rl:
    st.markdown(f"### ⏳ 强化学习时光机：{target}")
    st.caption("截断历史数据让AI盲猜，然后用未来数据打脸，逼迫其生成量化纪律，永久写入外脑。")
    
    col1, col2 = st.columns(2)
    with col1: start_d = st.date_input("盲测起点", datetime.date(2023, 1, 1))
    with col2: end_d = st.date_input("盲测终点(截断点)", datetime.date(2023, 6, 1))

    if st.button("🔥 启动闭门军演与自我进化", key="btn_rl"):
        with st.spinner("正在切割历史时间线..."):
            hist = yf.Ticker(target).history(start=start_d, end=end_d)
            if hist.empty:
                st.error("该时间段无数据")
            else:
                start_p = round(hist['Close'].iloc[0], 2)
                end_p = round(hist['Close'].iloc[-1], 2)
                
                # 抓取盲测终点之后 30 天的真实数据 (用于打脸验证)
                future = yf.Ticker(target).history(start=end_d, periods=30)
                future_p = round(future['Close'].iloc[-1], 2) if not future.empty else "未知"
                
                st.markdown(f"**📈 喂养数据**：{start_d} 至 {end_d}，股价从 {start_p} 变动至 {end_p}。")
                st.markdown(f"**🔮 现实毒打**：截断点后一个月，股价实际走到了 {future_p}。")
                
                rl_prompt = f"""
                在 {start_d} 到 {end_d}，{target} 股价从 {start_p} 到 {end_p}。
                你作为量化模型，如果当时在 {end_p} 这个位置，你会怎么操作？
                随后现实走势是：接下来的一个月股价来到了 {future_p}。
                请反思预测与现实的差距，并强制提炼一条不超过40个字的【硬核量化纪律】。最后请明确输出这条纪律。
                """
                
                st.markdown("### 🔴 DeepSeek 历史左右互搏流")
                # 这里我们先让流式显示出来
                call_deepseek_stream(rl_prompt)
                
                # 后台静默抓取纪律写入 JSON
                client = OpenAI(api_key=ds_key, base_url="https://api.deepseek.com/v1")
                res = client.chat.completions.create(
                    model="deepseek-chat", 
                    messages=[{"role": "user", "content": rl_prompt + "请只输出最后那条40字以内的纪律本身，不要其他任何废话。"}]
                ).choices[0].message.content
                
                save_lesson(f"【时光机验证 - {target}】: {res}")
                st.success(f"✅ 思想钢印已自动写入外脑库：{res}")

# ==========================================
# 模块 3：常规穿透 (带外脑读取)
# ==========================================
with tab_main:
    st.info("读取外脑数据进行常规分析...")
    if st.button(f"🚀 启动深度推演：{target}", key="btn_main"):
        with open(KNOWLEDGE_FILE, 'r', encoding='utf-8') as f:
            db = json.load(f)
        rules = "\n".join(db["reflections"])
        sys_inject = f"\n\n【必须遵守的系统外脑纪律】：\n{rules}" if rules else ""
        
        call_deepseek_stream(f"分析标的{target}，最新价{p}。结合基本面与以下纪律给出操作建议。{sys_inject}")
