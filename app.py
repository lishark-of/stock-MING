import streamlit as st
import yfinance as yf
from openai import OpenAI
import datetime
import json
import os
import time
import io

# ==========================================
# 1. 全局配置与极简美学 UI
# ==========================================
st.set_page_config(page_title="量化交易终端 V17.0", page_icon="🦈", layout="wide")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');
    .stApp { background-color: #F5F5F7; color: #1D1D1F; font-family: -apple-system, sans-serif; }
    .stButton>button { background-color: #1D1D1F; color: white; border-radius: 8px; border: none; width: 100%; font-weight: 500; transition: 0.2s; }
    .stButton>button:hover { background-color: #434343; color: white; }
    .stMetric { background-color: white; padding: 15px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.03); border: 1px solid #E5E5EA; }
    .risk-alert { background-color: #FFF0F0; padding: 15px; border-radius: 8px; border-left: 4px solid #FF3B30; margin-bottom: 10px; color: #FF3B30; font-weight: 600;}
    .knowledge-card { background-color: #ffffff; padding: 15px; border-radius: 8px; border-left: 4px solid #0071E3; margin-bottom: 10px; font-size: 0.9rem;}
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. 策略外脑 (RAG 本地数据库) 初始化
# ==========================================
KNOWLEDGE_FILE = "strategy_knowledge.json"

def init_knowledge_base():
    if not os.path.exists(KNOWLEDGE_FILE):
        with open(KNOWLEDGE_FILE, 'w', encoding='utf-8') as f:
            json.dump({"reflections": [], "strategies": []}, f)

def load_knowledge():
    with open(KNOWLEDGE_FILE, 'r', encoding='utf-8') as f: return json.load(f)

def save_knowledge(data):
    with open(KNOWLEDGE_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

init_knowledge_base()

# ==========================================
# 3. 核心功能与缓存提速优化 (Logic Optimization)
# ==========================================
# 优化点：缓存股票基础数据，避免频繁呼叫API导致卡顿或封禁
@st.cache_data(ttl=300)
def get_current_price(ticker):
    try:
        return round(yf.Ticker(ticker).history(period='1d')['Close'].iloc[0], 2)
    except:
        return None

@st.cache_data(ttl=3600)
def get_historical_data(ticker, start_str, end_str):
    try:
        return yf.Ticker(ticker).history(start=start_str, end=end_str)
    except:
        return pd.DataFrame()

def call_deepseek_stream(prompt, system_role="作为顶级量化基金经理。"):
    if 'ds_key' not in st.session_state or not st.session_state.ds_key: 
        return st.error("❌ 缺少 DeepSeek 密钥，请检查 Streamlit Secrets 配置。")
    try:
        client = OpenAI(api_key=st.session_state.ds_key, base_url="https://api.deepseek.com/v1")
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "system", "content": system_role}, {"role": "user", "content": prompt}],
            stream=True
        )
        st.write_stream((chunk.choices[0].delta.content or "") for chunk in response)
    except Exception as e:
        st.error(f"⚠️ 算力节点连接异常，请稍后再试。详细原因: {e}")

# ==========================================
# 4. 权限认证与系统登录
# ==========================================
if 'user_role' not in st.session_state: 
    st.session_state.user_role = None

if st.session_state.user_role is None:
    st.markdown("<h1 style='text-align: center; margin-top: 10vh;'>Terminal V17</h1>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        pwd = st.text_input("", type="password", placeholder="输入访问密钥", label_visibility="collapsed")
        if st.button("接入系统"):
            if pwd == "888888": st.session_state.user_role = "Admin"; st.rerun()
            elif pwd == "guest": st.session_state.user_role = "Guest"; st.rerun()
            else: st.error("密钥验证失败")
else:
    # 挂载密钥到 session_state 供全局调用
    try:
        st.session_state.ds_key = st.secrets["DEEPSEEK_API_KEY"]
    except:
        st.session_state.ds_key = None

    # ==========================================
    # 5. 全局指挥部 (主界面)
    # ==========================================
    st.title("机构级资产指挥台")
    top_c1, top_c2 = st.columns([3, 1])
    with top_c1: 
        target = st.text_input("输入全局侦测代码 (如 LITE, POET, 002008.SZ)", "LITE", label_visibility="collapsed").upper()
    with top_c2:
        price = get_current_price(target)
        p_display = f"$ {price}" if price and not target.endswith(('.SZ', '.SS')) else (f"¥ {price}" if price else "--")
        st.metric("卫星侦测价格", p_display)

    st.markdown("---")

    # 分区面板
    tab_risk, tab_rl, tab_main, tab_brain = st.tabs([
        "🛡️ 天眼风控 (排雷)", 
        "⏳ 炼丹炉 (强化学习)", 
        "📈 量化推演 (主干)", 
        "🧠 策略外脑 (数据中心)"
    ])

    # ------------------------------------------
    # 模块 A：天眼风控 (Alt-Data 排雷)
    # ------------------------------------------
    with tab_risk:
        st.markdown(f"### 🛡️ 极高权限合规审计：{target}")
        st.info("消耗算力扫描内幕交易、消息抢跑、监管问询等非财务治理风险。")
        
        if st.button("🚨 启动全网舆情风控网", key="btn_risk"):
            with st.spinner("正在渗透舆情数据源..."):
                try:
                    news_data = yf.Ticker(target).news
                    headlines = [n['title'] for n in news_data][:6] if news_data else "暂无强关联英文舆情"
                    
                    risk_prompt = f"""
                    你现在是 SEC 和中国证监会的顶级稽查员。标的：{target}。
                    最新接口抓取到的舆情线索：{headlines}。
                    请调动全网知识库，排查：
                    1. 该标的历史上是否存在‘公告前股价提前异动’或‘利好出尽暴跌’的劣迹？
                    2. 是否收到过监管关注函、问询函或遭到知名机构做空？
                    3. 若存在严重的信息违规或治理风险，请在开头用【一票否决】做出严厉警告并说明原因。
                    """
                    st.markdown("<div class='risk-alert'>正在执行深度排雷协议，请留意红色警告...</div>", unsafe_allow_html=True)
                    call_deepseek_stream(risk_prompt, system_role="作为无情的金融监管稽查机器，你的任务是找出标的背后的法律与治理暗雷。")
                except:
                    st.error("舆情接口抓取受限。")

    # ------------------------------------------
    # 模块 B：炼丹炉 (强化学习与纪律提取)
    # ------------------------------------------
    with tab_rl:
        st.markdown(f"### ⏳ 强化学习时光机：{target}")
        st.caption("截断历史数据让AI盲猜，用未来数据打脸，逼迫其生成量化纪律，永久写入系统外脑。")
        
        col1, col2 = st.columns(2)
        with col1: start_d = st.date_input("盲测起点", datetime.date(2023, 1, 1))
        with col2: end_d = st.date_input("盲测终点(截断点)", datetime.date(2023, 6, 1))

        if st.button("🔥 启动闭门军演", key="btn_rl"):
            with st.spinner("正在切割历史时间线..."):
                # 彻底修复 TypeError：强制转换为 yfinance 信任的格式
                s_str = start_d.strftime('%Y-%m-%d')
                e_str = end_d.strftime('%Y-%m-%d')
                
                hist = get_historical_data(target, s_str, e_str)
                
                if hist.empty:
                    st.warning("⚠️ 该时间段无数据。请确认股票在该时段已上市，或避开节假日。")
                else:
                    start_p = round(hist['Close'].iloc[0], 2)
                    end_p = round(hist['Close'].iloc[-1], 2)
                    
                    # 未来 30 天验证
                    future_d = end_d + datetime.timedelta(days=30)
                    f_str = future_d.strftime('%Y-%m-%d')
                    future = get_historical_data(target, e_str, f_str)
                    future_p = round(future['Close'].iloc[-1], 2) if not future.empty else "未知(退市或停牌)"
                    
                    st.markdown(f"**📈 喂养数据**：{s_str} 至 {e_str}，股价从 {start_p} 变动至 {end_p}。")
                    st.markdown(f"**🔮 现实毒打**：截断点后一个月，股价实际走到了 {future_p}。")
                    
                    rl_prompt = f"""
                    背景：在 {s_str} 到 {e_str}，{target} 股价从 {start_p} 变动到 {end_p}。
                    假设你当时在 {end_p} 这个位置，你会怎么操作？
                    现实：接下来的一个月股价来到了 {future_p}。
                    指令：反思预测与现实的差距，并强制提炼一条不超过40个字的【硬核量化纪律】。请明确输出这条纪律。
                    """
                    
                    st.markdown("### 🔴 历史左右互搏流")
                    call_deepseek_stream(rl_prompt)
                    
                    # 静默提取纪律并写入JSON
                    if st.session_state.ds_key:
                        try:
                            client = OpenAI(api_key=st.session_state.ds_key, base_url="https://api.deepseek.com/v1")
                            res = client.chat.completions.create(
                                model="deepseek-chat", 
                                messages=[{"role": "user", "content": rl_prompt + "请只输出最后那条40字以内的纪律本身，不要其他解释。"}]
                            ).choices[0].message.content
                            
                            db = load_knowledge()
                            db["reflections"].append(f"【时光机验证 - {target}】: {res}")
                            save_knowledge(db)
                            st.success(f"✅ 思想钢印已自动写入外脑库：{res}")
                        except: pass

    # ------------------------------------------
    # 模块 C：主干量化推演 (带 RAG 外脑注入)
    # ------------------------------------------
    with tab_main:
        st.markdown(f"### 📈 实时量化穿透：{target}")
        if st.button("🚀 启动深度推演", key="btn_main"):
            db = load_knowledge()
            rules = "\n".join(db["strategies"] + db["reflections"])
            sys_inject = f"\n\n【⚠️必须遵守的系统外脑纪律】：请严格结合以下规则进行评判：\n{rules}" if rules else "\n\n(当前系统外脑为空，执行标准推演)"
            
            p_val = price if price else "未知"
            call_deepseek_stream(f"分析标的 {target}，最新价 {p_val}。结合基本面、资金博弈与以下纪律给出精确的操作建议。{sys_inject}")

    # ------------------------------------------
    # 模块 D：策略外脑数据中心
   # ------------------------------------------
    # 模块 D：策略外脑数据中心 (V18.0 文档投喂版)
    # ------------------------------------------
    with tab_brain:
        st.markdown("### 🧬 RAG 向量记忆中心")
        st.caption("支持手动喂养，或直接上传 Word/PPT 研报，AI将自动榨取核心量化战法。")
        
        c_feed1, c_feed2 = st.columns([1, 1])
        
        # --- 方式 1：手动文本投喂 ---
        with c_feed1:
            st.markdown("**📝 1. 碎片战法投喂 (纯文本)**")
            feed_text = st.text_area("粘贴聊天记录或大白话", placeholder="例如：CPO板块连续三天缩量阴跌后，第四天早盘急杀可捞底...")
            if st.button("🧠 提炼文本并刻入外脑", key="btn_text_feed"):
                if feed_text and st.session_state.ds_key:
                    with st.spinner("正在提炼规则..."):
                        client = OpenAI(api_key=st.session_state.ds_key, base_url="https://api.deepseek.com/v1")
                        res = client.chat.completions.create(
                            model="deepseek-chat", 
                            messages=[{"role": "user", "content": f"将以下内容转化为一条极其精简、冷酷的量化纪律(不超过50字)：{feed_text}"}]
                        ).choices[0].message.content
                        
                        db = load_knowledge()
                        db["strategies"].append(f"【手动植入】: {res}")
                        save_knowledge(db)
                        st.success("✅ 战法已永久写入系统底层！")
                        time.sleep(1)
                        st.rerun()
                elif not st.session_state.ds_key: st.error("缺少 API Key。")

        # --- 方式 2：文档自动榨取 (新功能) ---
        with c_feed2:
            st.markdown("**📂 2. 机构研报/课件投喂**")
            uploaded_file = st.file_uploader("支持 .docx, .pptx, .txt 格式", type=['docx', 'pptx', 'txt'])
            
            if st.button("🧬 启动文档深度榨取", key="btn_doc_feed"):
                if uploaded_file is not None and st.session_state.ds_key:
                    with st.spinner("正在强行破译文档排版，提取底层文字..."):
                        extracted_text = ""
                        try:
                            # 1. 解析 Word
                            if uploaded_file.name.endswith('.docx'):
                                import docx
                                doc = docx.Document(uploaded_file)
                                extracted_text = "\n".join([p.text for p in doc.paragraphs if p.text])
                            
                            # 2. 解析 PPT
                            elif uploaded_file.name.endswith('.pptx'):
                                import pptx
                                ppt = pptx.Presentation(uploaded_file)
                                for slide in ppt.slides:
                                    for shape in slide.shapes:
                                        if hasattr(shape, "text"):
                                            extracted_text += shape.text + "\n"
                            
                            # 3. 解析 TXT
                            elif uploaded_file.name.endswith('.txt'):
                                extracted_text = uploaded_file.getvalue().decode("utf-8")

                            # --- 交给 DeepSeek 榨取 ---
                            if not extracted_text.strip():
                                st.warning("文档似乎是空的或全是图片，无法提取文字。")
                            else:
                                st.info(f"成功提取 {len(extracted_text)} 字情报，正在呼叫 DeepSeek 进行降维打击...")
                                # 为防止研报太长爆 Token，截取前 20000 字
                                safe_text = extracted_text[:20000] 
                                
                                client = OpenAI(api_key=st.session_state.ds_key, base_url="https://api.deepseek.com/v1")
                                prompt = f"""
                                你是一个冷酷的量化策略提取器。请从以下券商研报/游资课件中，榨取出最核心的、带有触发条件的【量化纪律/交易规则】。
                                要求：
                                1. 提炼为 2-4 条最硬核的规则。
                                2. 每条严格控制在 50 字以内。
                                3. 不要任何废话，直接按行输出结果。
                                文档内容：{safe_text}
                                """
                                res = client.chat.completions.create(
                                    model="deepseek-chat", 
                                    messages=[{"role": "user", "content": prompt}]
                                ).choices[0].message.content
                                
                                # 写入外脑
                                db = load_knowledge()
                                new_rules = [r.strip() for r in res.split('\n') if r.strip() and len(r)>5]
                                for rule in new_rules:
                                    # 自动打上文件名标签，方便以后追溯
                                    db["strategies"].append(f"【研报-{uploaded_file.name[:6]}】: {rule}")
                                save_knowledge(db)
                                
                                st.success(f"✅ 成功榨取并写入 {len(new_rules)} 条硬核战法！")
                                time.sleep(1.5)
                                st.rerun()

                        except Exception as e:
                            st.error(f"文档解析失败: {e} (提示：请确保已在 requirements.txt 中安装 python-docx 和 python-pptx)")
                elif not st.session_state.ds_key: st.error("缺少 API Key。")
                else: st.warning("请先上传文件！")
        
        st.markdown("---")
        st.markdown("**📚 当前系统脑容量 (已掌握的纪律)**")
        db = load_knowledge()
        all_rules = db["strategies"] + db["reflections"]
        if all_rules:
            for rule in all_rules:
                st.markdown(f"<div class='knowledge-card'>⚙️ {rule}</div>", unsafe_allow_html=True)
        else:
            st.info("当前系统外脑是一张白纸。")
