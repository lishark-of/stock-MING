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
            # ✨ 新增：带 ID 读取的云端查询（为了精准删除）
    def get_all_cloud_memories():
        if not supabase: return []
        try:
            # 按照写入时间倒序排列，最新的在最上面
            res = supabase.table("brain_memory").select("id, memory_type, content").order("id", desc=True).execute()
            return res.data
        except Exception as e:
            st.error(f"云端读取异常: {e}")
            return []

    # ✨ 新增：云端抹除函数
    def delete_cloud_memories(ids_to_delete):
        if not supabase or not ids_to_delete: return
        try:
            # 使用 in_ 方法批量删除选中的 ID
            supabase.table("brain_memory").delete().in_("id", ids_to_delete).execute()
        except Exception as e:
            st.error(f"云端抹除异常: {e}")

    # ==========================================
    # ==========================================
    # 4. 全局指挥部 (主界面) - V21.0 智能识别版
    # ==========================================
    st.title("机构级资产指挥台")
    
    top_c1, top_c2 = st.columns([3, 1])
    with top_c1: 
        # 用户现在只需要输入纯数字或纯字母
        raw_target = st.text_input("🎯 锁定目标 (支持纯数字如 600459，或美股 LITE)", "LITE", label_visibility="collapsed").upper().strip()
        
        # ✨ 智能后缀补全引擎
        target = raw_target
        market_badge = "🇺🇸 美股/其他"
        if raw_target.isdigit() and len(raw_target) == 6:
            if raw_target.startswith('6'):
                target = f"{raw_target}.SS"
                market_badge = "🇨🇳 A股 (沪)"
            elif raw_target.startswith(('0', '3')):
                target = f"{raw_target}.SZ"
                market_badge = "🇨🇳 A股 (深)"

    with top_c2:
        price = get_current_price(target)
        if price:
            p_display = f"¥ {price}" if "🇨🇳" in market_badge else f"$ {price}"
            st.metric(f"📡 卫星报价 ({market_badge})", p_display)
        else:
            st.metric(f"📡 信号丢失 ({market_badge})", "未查找到该标的")

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
   # ------------------------------------------
    # 模块 C：主干量化推演 & 巨鲸追踪 (V21.0 双引擎版)
    # ------------------------------------------
    with tab_main:
        st.markdown(f"### 📈 实时穿透：{target}")
        
        # 增加并排的两个控制按钮
        col_main1, col_main2 = st.columns(2)
        
        # 按钮一：常规推演
        with col_main1:
            btn_normal = st.button("🚀 启动外脑深度推演", use_container_width=True)
            
        # 按钮二：资金追踪 (消耗 Token)
        with col_main2:
            btn_whale = st.button("🐳 巨鲸资金嗅探 (深度算力)", type="primary", use_container_width=True)

        # --- 逻辑 1：外脑常规推演 (深度扩容版) ---
        if btn_normal:
            with st.spinner("正在从云端调取适配当前市场的量化纪律..."):
                db = load_cloud_knowledge() 
                all_rules = db["strategies"] + db["reflections"]
                is_a_share = target.endswith(('.SZ', '.SS', '.sz', '.ss'))
                
                filtered_rules = [r for r in all_rules if not (is_a_share and "🇺🇸" in r) and not (not is_a_share and "🇨🇳" in r)]
                rules_text = "\n".join(filtered_rules)
                sys_inject = f"\n\n【系统外脑记忆库】：\n{rules_text}" if rules_text else "\n\n(当前市场云端外脑为空)"
            
            p_val = price if price else "未知"
            # ✨ 升级点 1：强制要求字数、结构，强制展开四大维度
            improved_prompt = f"""
            你是一位杀伐果断的顶级量化基金经理。请对标的 {target}（最新价 {p_val}）出具一份【极度详尽、深度穿透】的量化研报（要求不少于800字，分点论述）。
            
            【你的原生任务】：
            请务必优先基于你自身庞大的金融知识库，按以下四大模块进行极其深度的拆解：
            1. 核心基本面与产业链地位（核心业务逻辑是什么？当前处于什么周期拐点？）
            2. 宏观与大面情绪共振（结合当前大盘情绪，该股是否存在错杀或估值溢价？）
            3. 筹码断层与微观技术面（强支撑位、阻力位、做T空间在哪里？）
            4. 极度精确的量化操作指令（必须包含明确的操作建议和精确到小数点的止损止盈位）。
            
            【外脑调用原则（至关重要）】：
            下方是【系统外脑记忆库】。请智能甄别：与 {target} 核心业务无关的板块纪律直接在脑内屏蔽（切勿在报告中提及不匹配），完全契合的作为核心操作依据并在报告中加粗。
            {sys_inject}
            """
            call_deepseek_stream(improved_prompt)

        # --- 逻辑 2：巨鲸资金追踪 (机构+盘口双引擎版) ---
        if btn_whale:
            with st.spinner("正在调动高阶算力，穿透明星机构底牌与交易异动..."):
                hist_5d = get_historical_data(target, (datetime.datetime.now() - datetime.timedelta(days=10)).strftime('%Y-%m-%d'), datetime.datetime.now().strftime('%Y-%m-%d'))
                volume_data = "近期无数据"
                if not hist_5d.empty:
                    recent_data = hist_5d[['Close', 'Volume']].tail(5)
                    volume_data = recent_data.to_string()
                
                p_val = price if price else "未知"
                # ✨ 升级点 2：强制要求挖掘公募、游资、明星基金经理的宏观动向
                whale_prompt = f"""
                你现在是华尔街与陆家嘴最顶级的“巨鲸资金流向嗅探犬”。
                标的：{target}。当前价：{p_val}。
                
                请你消耗最大算力，执行【宏观机构与微观盘口双重穿透】：
                
                第一部分：【宏观机构底牌深挖】
                请立刻调动你的全网知识库，深挖该标的背后的机构博弈逻辑。
                指出该标的通常受哪些“明星基金经理”、“国家队/社保/公募机构”或“顶级游资/外资（北向）”的青睐？
                结合它近期的资本动作，推演这些顶流大资金目前是在潜伏建仓、锁仓不动，还是在逢高派发？
                
                第二部分：【微观盘口解剖】
                以下是该标的最近 5 个交易日的【收盘价与成交量】真实微观数据：
                {volume_data}
                结合以上量价数据，验证你第一部分的推演。是否存在放量滞涨、缩量企稳等盘口特征？主力资金近几天是在洗盘还是恐慌出逃？
                
                第三部分：【巨鲸追踪结论】
                给出极其冷血的跟庄或避险建议。
                """
                st.markdown("<div class='risk-alert' style='border-left-color: #007AFF; color: #007AFF;'>🐳 已锁定巨鲸声呐信号，正在解码机构大户意图...</div>", unsafe_allow_html=True)
                call_deepseek_stream(whale_prompt, system_role="作为一台拥有全网视野、没有感情的盘口与机构解剖机器。")
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
        st.markdown("**🗑️ 外脑记忆管理中心 (圈选并物理抹除)**")
        
        # 获取所有带 ID 的记忆记录
        all_records = get_all_cloud_memories()
        
        if all_records:
            # 构建一个字典，把记录的 ID 映射到它的具体内容上，方便在多选框里展示
            options_dict = {record['id']: record['content'] for record in all_records}
            
            # 圈选多选框
            selected_ids = st.multiselect(
                "请选择需要从云端剔除的过期纪律：",
                options=list(options_dict.keys()),
                format_func=lambda x: options_dict[x], # 让选项显示具体文字，而不是冷冰冰的数字ID
                placeholder="点击下拉框查看并圈选..."
            )
            
            # 删除按钮
            if st.button("🔥 彻底抹除选中的记忆", type="primary"):
                if selected_ids:
                    with st.spinner("正在向云端发送物理擦除指令..."):
                        delete_cloud_memories(selected_ids)
                        st.success("✅ 记忆已彻底从云端矩阵中剔除！")
                        time.sleep(1)
                        st.rerun()
                else:
                    st.warning("⚠️ 请先圈选你要删除的纪律。")
            
            st.markdown("---")
            st.markdown("**📚 当前生效的系统脑容量**")
            for record in all_records:
                st.markdown(f"<div class='knowledge-card'>{record['content']}</div>", unsafe_allow_html=True)
        else:
            st.info("当前云端外脑是一张白纸，快去喂养数据吧！")
