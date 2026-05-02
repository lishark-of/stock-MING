import streamlit as st
import yfinance as yf
from openai import OpenAI
from supabase import create_client, Client # ✨ 新增：云端数据库引擎
import datetime
import os
import time
import io

# ==========================================
# 1. 全局配置与极简美学 UI
# ==========================================
st.set_page_config(page_title="量化交易终端 V19.0 云端版", page_icon="🦈", layout="wide")

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
# 2. 核心功能与缓存提速优化 
# ==========================================
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
# 3. 权限认证与 Supabase 云端连线
# ==========================================
if 'user_role' not in st.session_state: 
    st.session_state.user_role = None

if st.session_state.user_role is None:
    st.markdown("<h1 style='text-align: center; margin-top: 10vh;'>Terminal V19 (Cloud)</h1>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        pwd = st.text_input("", type="password", placeholder="输入访问密钥", label_visibility="collapsed")
        if st.button("接入系统"):
            if pwd == "888888": st.session_state.user_role = "Admin"; st.rerun()
            elif pwd == "guest": st.session_state.user_role = "Guest"; st.rerun()
            else: st.error("密钥验证失败")
else:
    # ✨ 挂载所有密钥并初始化 Supabase 云端
    try:
        st.session_state.ds_key = st.secrets["DEEPSEEK_API_KEY"]
        sb_url = st.secrets["SUPABASE_URL"]
        sb_key = st.secrets["SUPABASE_KEY"]
        supabase: Client = create_client(sb_url, sb_key)
    except Exception as e:
        st.session_state.ds_key = None
        supabase = None
        st.error(f"⚠️ 云端配置缺失，请检查 Secrets。详细报错: {e}")

    # ✨ 云端增删改查函数 (彻底替代旧版 JSON)
    def load_cloud_knowledge():
        if not supabase: return {"strategies": [], "reflections": []}
        try:
            res = supabase.table("brain_memory").select("*").execute()
            data = res.data
            return {
                "strategies": [d['content'] for d in data if d['memory_type'] == 'strategy'],
                "reflections": [d['content'] for d in data if d['memory_type'] == 'reflection']
            }
        except Exception as e:
            st.error(f"云端读取异常: {e}")
            return {"strategies": [], "reflections": []}

    def insert_cloud_memory(m_type, content):
        if not supabase: return
        try:
            supabase.table("brain_memory").insert({"memory_type": m_type, "content": content}).execute()
        except Exception as e:
            st.error(f"云端写入异常: {e}")

    # ==========================================
    # 4. 全局指挥部 (主界面)
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

    tab_risk, tab_rl, tab_main, tab_brain = st.tabs([
        "🛡️ 天眼风控 (排雷)", 
        "⏳ 炼丹炉 (强化学习)", 
        "📈 量化推演 (主干)", 
        "☁️ 云端外脑 (数据中心)"
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
                s_str = start_d.strftime('%Y-%m-%d')
                e_str = end_d.strftime('%Y-%m-%d')
                
                hist = get_historical_data(target, s_str, e_str)
                
                if hist.empty:
                    st.warning("⚠️ 该时间段无数据。请确认股票在该时段已上市，或避开节假日。")
                else:
                    start_p = round(hist['Close'].iloc[0], 2)
                    end_p = round(hist['Close'].iloc[-1], 2)
                    
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
                    
                    # ✨ 静默提取纪律并极速写入 Supabase 云端
                    if st.session_state.ds_key:
                        try:
                            client = OpenAI(api_key=st.session_state.ds_key, base_url="https://api.deepseek.com/v1")
                            res = client.chat.completions.create(
                                model="deepseek-chat", 
                                messages=[{"role": "user", "content": rl_prompt + "请只输出最后那条40字以内的纪律本身，不要其他解释。"}]
                            ).choices[0].message.content
                            
                            insert_cloud_memory("reflection", f"【时光机验证 - {target}】: {res}")
                            st.success(f"✅ 思想钢印已自动写入云端数据库：{res}")
                        except Exception as e: st.error(f"云端记录失败: {e}")

    # ------------------------------------------
    # 模块 C：主干量化推演 (带 云端外脑注入)
    # ------------------------------------------
    with tab_main:
        st.markdown(f"### 📈 实时量化穿透：{target}")
        if st.button("🚀 启动深度推演", key="btn_main"):
            with st.spinner("正在从云端调取量化纪律..."):
                db = load_cloud_knowledge() # ✨ 从云端读取
                rules = "\n".join(db["strategies"] + db["reflections"])
                sys_inject = f"\n\n【⚠️必须遵守的系统云端纪律】：请严格结合以下规则进行评判：\n{rules}" if rules else "\n\n(当前系统云端外脑为空，执行标准推演)"
            
            p_val = price if price else "未知"
            call_deepseek_stream(f"分析标的 {target}，最新价 {p_val}。结合基本面、资金博弈与以下纪律给出精确的操作建议。{sys_inject}")

    # ------------------------------------------
    # 模块 D：策略外脑数据中心 (V19.0 云端全解析版)
    # ------------------------------------------
    with tab_brain:
        st.markdown("### ☁️ 云端 RAG 向量记忆中心 (Supabase驱动)")
        st.caption("支持手动喂养，或直接上传 PDF/Word/PPT 研报，AI将自动榨取战法并永久保存在加州的服务器上。")
        
        c_feed1, c_feed2 = st.columns([1, 1])
        
        # --- 方式 1：手动文本投喂 ---
        with c_feed1:
            st.markdown("**📝 1. 碎片战法投喂 (纯文本)**")
            feed_text = st.text_area("粘贴聊天记录或大白话", placeholder="例如：CPO板块连续三天缩量阴跌后，第四天早盘急杀可捞底...")
            if st.button("🧠 提炼文本并刻入云端", key="btn_text_feed"):
                if feed_text and st.session_state.ds_key:
                    with st.spinner("正在提炼规则并连接数据库..."):
                        client = OpenAI(api_key=st.session_state.ds_key, base_url="https://api.deepseek.com/v1")
                        res = client.chat.completions.create(
                            model="deepseek-chat", 
                            messages=[{"role": "user", "content": f"将以下内容转化为一条极其精简、冷酷的量化纪律(不超过50字)：{feed_text}"}]
                        ).choices[0].message.content
                        
                        insert_cloud_memory("strategy", f"【手动植入】: {res}") # ✨ 写入云端
                        st.success("✅ 战法已永久写入云端底层！")
                        time.sleep(1)
                        st.rerun()
                elif not st.session_state.ds_key: st.error("缺少 API Key。")

        # --- 方式 2：文档自动榨取 ---
        with c_feed2:
            st.markdown("**📂 2. 机构研报/课件投喂**")
            uploaded_file = st.file_uploader("支持 .pdf, .docx, .pptx, .txt 格式", type=['pdf', 'docx', 'pptx', 'txt'])
            
            if st.button("🧬 启动文档深度榨取", key="btn_doc_feed"):
                if uploaded_file is not None and st.session_state.ds_key:
                    with st.spinner("正在强行破译文档排版，提取底层文字..."):
                        extracted_text = ""
                        try:
                            # 1. 解析 PDF
                            if uploaded_file.name.endswith('.pdf'):
                                import PyPDF2
                                pdf_reader = PyPDF2.PdfReader(uploaded_file)
                                for page in pdf_reader.pages:
                                    text = page.extract_text()
                                    if text: extracted_text += text + "\n"

                            # 2. 解析 Word
                            elif uploaded_file.name.endswith('.docx'):
                                import docx
                                doc = docx.Document(uploaded_file)
                                extracted_text = "\n".join([p.text for p in doc.paragraphs if p.text])
                            
                            # 3. 解析 PPT
                            elif uploaded_file.name.endswith('.pptx'):
                                import pptx
                                ppt = pptx.Presentation(uploaded_file)
                                for slide in ppt.slides:
                                    for shape in slide.shapes:
                                        if hasattr(shape, "text"):
                                            extracted_text += shape.text + "\n"
                            
                            # 4. 解析 TXT
                            elif uploaded_file.name.endswith('.txt'):
                                extracted_text = uploaded_file.getvalue().decode("utf-8")
                                
                            # --- 交给 DeepSeek 榨取 ---
                            if not extracted_text.strip():
                                st.warning("文档似乎是空的或全是图片，无法提取文字。")
                            else:
                                st.info(f"成功提取 {len(extracted_text)} 字情报，正在呼叫 DeepSeek 进行降维打击...")
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
                                
                                # ✨ 写入云端
                                new_rules = [r.strip() for r in res.split('\n') if r.strip() and len(r)>5]
                                for rule in new_rules:
                                    insert_cloud_memory("strategy", f"【研报-{uploaded_file.name[:6]}】: {rule}")
                                
                                st.success(f"✅ 成功榨取并写入 {len(new_rules)} 条硬核战法至云端！")
                                time.sleep(1.5)
                                st.rerun()

                        except Exception as e:
                            st.error(f"文档解析或云端传输失败: {e} (提示：请确保已安装 PyPDF2, python-docx, python-pptx)")
                elif not st.session_state.ds_key: st.error("缺少 API Key。")
                else: st.warning("请先上传文件！")
        
        st.markdown("---")
        st.markdown("**📚 云端数据库容量监控 (实时同步)**")
        db = load_cloud_knowledge() # ✨ 实时调取云端
        all_rules = db["strategies"] + db["reflections"]
        if all_rules:
            for rule in all_rules:
                st.markdown(f"<div class='knowledge-card'>☁️ {rule}</div>", unsafe_allow_html=True)
        else:
            st.info("当前云端外脑是一张白纸。快去喂养数据吧！")
