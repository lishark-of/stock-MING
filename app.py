import streamlit as st
import yfinance as yf
from openai import OpenAI
from supabase import create_client, Client
import datetime
import os
import time
import io
import pandas as pd
import numpy as np

# ==========================================
# 1. 全局配置与极简美学 UI
# ==========================================
st.set_page_config(page_title="量化交易终端 V21.0 超级引擎版", page_icon="🦈", layout="wide")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');
    .stApp { background-color: #F5F5F7; color: #1D1D1F; font-family: -apple-system, sans-serif; }
    .stButton>button { background-color: #1D1D1F; color: white; border-radius: 8px; border: none; width: 100%; font-weight: 500; transition: 0.2s; }
    .stButton>button:hover { background-color: #434343; color: white; }
    .stMetric { background-color: white; padding: 15px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.03); border: 1px solid #E5E5EA; }
    .risk-alert { background-color: #FFF0F0; padding: 15px; border-radius: 8px; border-left: 4px solid #FF3B30; margin-bottom: 10px; color: #FF3B30; font-weight: 600;}
    .knowledge-card { background-color: #ffffff; padding: 15px; border-radius: 8px; border-left: 4px solid #0071E3; margin-bottom: 10px; font-size: 0.9rem;}
    .us-card { background-color: #F0F7FF; padding: 15px; border-radius: 8px; border-left: 4px solid #0071E3; margin-bottom: 10px; }
    .cn-card { background-color: #FFF8F0; padding: 15px; border-radius: 8px; border-left: 4px solid #FF6B35; margin-bottom: 10px; }
    .token-counter { background-color: #FFE5E5; padding: 10px; border-radius: 8px; font-size: 0.85rem; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 📊 Token 消耗计数器（可选记录）
# ==========================================
if 'token_usage' not in st.session_state:
    st.session_state.token_usage = {
        'deepseek_calls': 0,
        'estimated_tokens': 0
    }

def log_token_usage(prompt_tokens_estimate=2000, completion_tokens_estimate=1500):
    """简单的 Token 消耗估算"""
    st.session_state.token_usage['deepseek_calls'] += 1
    st.session_state.token_usage['estimated_tokens'] += (prompt_tokens_estimate + completion_tokens_estimate)

# ==========================================
# 2. 核心功能与缓存���速优化 
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
        data = yf.Ticker(ticker).history(start=start_str, end=end_str)
        if data.empty:
            return pd.DataFrame()
        return data
    except:
        return pd.DataFrame()

def call_deepseek_stream(prompt, system_role="作为顶级量化基金经理。"):
    if 'ds_key' not in st.session_state or not st.session_state.ds_key: 
        return st.error("❌ 缺少 DeepSeek 密钥，请检查 Streamlit Secrets 配置。")
    try:
        log_token_usage()
        client = OpenAI(api_key=st.session_state.ds_key, base_url="https://api.deepseek.com/v1")
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "system", "content": system_role}, {"role": "user", "content": prompt}],
            stream=True,
            temperature=0.7,
            max_tokens=4000
        )
        st.write_stream((chunk.choices[0].delta.content or "") for chunk in response)
    except Exception as e:
        st.error(f"⚠️ 算力节点连接异常，请稍后再试。详细原因: {e}")

def call_deepseek_non_stream(prompt, system_role="作为顶级量化基金经理。", max_tokens=2000):
    """非流式调用，返回完整文本（用于数据提取）"""
    if 'ds_key' not in st.session_state or not st.session_state.ds_key: 
        return None
    try:
        log_token_usage()
        client = OpenAI(api_key=st.session_state.ds_key, base_url="https://api.deepseek.com/v1")
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "system", "content": system_role}, {"role": "user", "content": prompt}],
            stream=False,
            temperature=0.5,
            max_tokens=max_tokens
        )
        return response.choices[0].message.content
    except Exception as e:
        st.error(f"⚠️ DeepSeek 调用失败: {e}")
        return None

# ==========================================
# 3. 权限认证�� Supabase 云端连线
# ==========================================
if 'user_role' not in st.session_state: 
    st.session_state.user_role = None

if st.session_state.user_role is None:
    st.markdown("<h1 style='text-align: center; margin-top: 10vh;'>Terminal V21 (超级引擎·无限Token)</h1>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        pwd = st.text_input("", type="password", placeholder="输入访问密钥", label_visibility="collapsed")
        if st.button("接入系统"):
            if pwd == "888888": st.session_state.user_role = "Admin"; st.rerun()
            elif pwd == "guest": st.session_state.user_role = "Guest"; st.rerun()
            else: st.error("密钥验证失败")
else:
    # ✨ 挂载��有密钥并初始化 Supabase 云端
    try:
        st.session_state.ds_key = st.secrets["DEEPSEEK_API_KEY"]
        sb_url = st.secrets["SUPABASE_URL"]
        sb_key = st.secrets["SUPABASE_KEY"]
        supabase: Client = create_client(sb_url, sb_key)
    except Exception as e:
        st.session_state.ds_key = None
        supabase = None
        st.error(f"⚠️ 云端配置缺失，请检查 Secrets。详细报错: {e}")

    # ✨ 云端增删改查函数
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

    def get_all_cloud_memories():
        if not supabase: return []
        try:
            res = supabase.table("brain_memory").select("id, memory_type, content").order("id", desc=True).execute()
            return res.data
        except Exception as e:
            st.error(f"云端读取异常: {e}")
            return []

    def delete_cloud_memories(ids_to_delete):
        if not supabase or not ids_to_delete: return
        try:
            supabase.table("brain_memory").delete().in_("id", ids_to_delete).execute()
        except Exception as e:
            st.error(f"云端抹除异常: {e}")

    # ==========================================
    # ✨✨✨ 超强美股引擎（Token 无限消耗）✨✨✨
    # ==========================================
    
    @st.cache_data(ttl=600)
    def compute_us_tech_signals(ticker):
        """华尔街技术面：MACD + RSI"""
        try:
            hist = get_historical_data(ticker, 
                (datetime.datetime.now() - datetime.timedelta(days=252)).strftime('%Y-%m-%d'),
                datetime.datetime.now().strftime('%Y-%m-%d'))
            
            if hist.empty or len(hist) < 26:
                return None
            
            delta = hist['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            
            exp1 = hist['Close'].ewm(span=12, adjust=False).mean()
            exp2 = hist['Close'].ewm(span=26, adjust=False).mean()
            macd = exp1 - exp2
            signal = macd.ewm(span=9, adjust=False).mean()
            histogram = macd - signal
            
            latest_rsi = rsi.iloc[-1]
            latest_macd = macd.iloc[-1]
            latest_signal = signal.iloc[-1]
            latest_histogram = histogram.iloc[-1]
            
            return {
                'rsi': round(latest_rsi, 2),
                'macd': round(latest_macd, 4),
                'signal': round(latest_signal, 4),
                'histogram': round(latest_histogram, 4),
                'rsi_status': 'OVERBOUGHT(>70)' if latest_rsi > 70 else ('OVERSOLD(<30)' if latest_rsi < 30 else 'NEUTRAL'),
                'macd_status': 'BULLISH_CROSS' if latest_histogram > 0 and histogram.iloc[-2] <= 0 else ('BEARISH_CROSS' if latest_histogram < 0 and histogram.iloc[-2] >= 0 else ('STRONG_BULL' if latest_histogram > 0 else 'STRONG_BEAR')),
            }
        except:
            return None

    @st.cache_data(ttl=1800)
    def fetch_us_options_signal(ticker):
        """美股期权市场情报"""
        try:
            stock = yf.Ticker(ticker)
            expirations = stock.options
            
            if not expirations:
                return None
            
            exp_date = expirations[0]
            opt = stock.option_chain(exp_date)
            calls = opt.calls
            puts = opt.puts
            
            call_iv_mean = calls['impliedVolatility'].mean() if not calls.empty else 0
            put_iv_mean = puts['impliedVolatility'].mean() if not puts.empty else 0
            
            iv_skew = round((put_iv_mean - call_iv_mean) * 100, 1) if call_iv_mean > 0 else 0
            
            total_oi = calls['openInterest'].sum()
            key_strike = calls.loc[calls['openInterest'].idxmax(), 'strike'] if len(calls) > 0 else None
            
            return {
                'expiration': exp_date,
                'call_iv': round(call_iv_mean, 3),
                'put_iv': round(put_iv_mean, 3),
                'iv_skew': iv_skew,
                'key_strike': round(key_strike, 2) if key_strike else None,
                'total_open_interest': int(total_oi),
                'skew_signal': 'FEAR_HEDGE(机构在套保)' if iv_skew > 15 else ('GREED_ATTACK(机构在进攻)' if iv_skew < -15 else 'NEUTRAL'),
            }
        except:
            return None

    @st.cache_data(ttl=3600)
    def fetch_us_institutional_data(ticker):
        """美股机构持仓"""
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            
            inst_pct = info.get('institutionalsHoldersPercent', None)
            insider_pct = info.get('insidersPercent', None)
            
            return {
                'inst_pct': round(inst_pct * 100, 2) if inst_pct else None,
                'insider_pct': round(insider_pct * 100, 2) if insider_pct else None,
                'inst_signal': '机构控盘(>60%)' if inst_pct and inst_pct > 0.6 else ('机构主流(40-60%)' if inst_pct and inst_pct > 0.4 else '分散持仓(<40%)') if inst_pct else '数据缺失',
            }
        except:
            return None

    def display_us_stock_analysis(target, price):
        """完整的美股华尔街分析界面"""
        st.markdown("#### 🇺🇸 华尔街机构三层穿透系统")
        
        # 第一层：技术面
        st.markdown("**第一层：技术面信号（MACD + RSI）**")
        signals = compute_us_tech_signals(target)
        
        if signals:
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                rsi_color = "🔴" if signals['rsi'] > 70 else ("🟢" if signals['rsi'] < 30 else "🟡")
                st.metric(f"{rsi_color} RSI-14", signals['rsi'], signals['rsi_status'])
            with col2:
                st.metric("📊 MACD", signals['macd'], "")
            with col3:
                st.metric("📈 Signal", signals['signal'], "")
            with col4:
                macd_color = "🟢" if signals['histogram'] > 0 else "🔴"
                st.metric(f"{macd_color} Histogram", signals['histogram'], signals['macd_status'])
            
            if signals['macd_status'] == 'BULLISH_CROSS':
                st.success("✅ **金叉信号激活**：短期看多，华尔街操盘手常在此建仓")
            elif signals['macd_status'] == 'BEARISH_CROSS':
                st.error("❌ **死叉信号激活**：短期看空，风险示警")
        else:
            st.warning("无法获取该股票的技术面数据")
        
        st.markdown("---")
        
        # 第二层：期权市场
        st.markdown("**第二层：期权市场隐含信号**")
        opt_signal = fetch_us_options_signal(target)
        
        if opt_signal:
            col_opt1, col_opt2, col_opt3 = st.columns(3)
            with col_opt1:
                st.metric("Call IV", opt_signal['call_iv'], "")
                st.metric("Put IV", opt_signal['put_iv'], "")
            with col_opt2:
                skew_color = "🔴" if opt_signal['iv_skew'] > 15 else ("🟢" if opt_signal['iv_skew'] < -15 else "🟡")
                st.metric(f"{skew_color} IV Skew", f"{opt_signal['iv_skew']}%", opt_signal['skew_signal'])
            with col_opt3:
                current = price if price else "N/A"
                st.metric(f"📍 Key Strike", f"${opt_signal['key_strike']}", f"vs ${current}")
        else:
            st.warning("该股票期权数据不可用")
        
        st.markdown("---")
        
        # 第三层：机构持仓
        st.markdown("**第三层：机构持仓战争**")
        inst_data = fetch_us_institutional_data(target)
        
        if inst_data and inst_data['inst_pct']:
            col_inst1, col_inst2 = st.columns(2)
            with col_inst1:
                if inst_data['inst_pct'] > 60:
                    st.success(f"✅ 机构重兵布防：{inst_data['inst_pct']}%")
                elif inst_data['inst_pct'] > 40:
                    st.info(f"🟡 机构主流持仓：{inst_data['inst_pct']}%")
                else:
                    st.warning(f"⚠️ 机构撤离迹象：{inst_data['inst_pct']}%")
        
        st.markdown("---")

    def display_cn_stock_analysis(target, price):
        """A股深度量化研报"""
        
        col_cn1, col_cn2 = st.columns(2)
        
        with col_cn1:
            btn_deepseek = st.button("🚀 启动外脑深度推演（A股专用）", use_container_width=True, key="btn_cn_deepseek")
        
        with col_cn2:
            btn_whale = st.button("🐳 巨鲸资金嗅探", type="primary", use_container_width=True, key="btn_cn_whale")
        
        if btn_deepseek:
            with st.spinner("正在从云端调取适配当前市场的量化纪律..."):
                db = load_cloud_knowledge() 
                all_rules = db["strategies"] + db["reflections"]
                filtered_rules = [r for r in all_rules if "🇨🇳" in r or "A股" in r or "沪深" in r]
                rules_text = "\n".join(filtered_rules)
                sys_inject = f"\n\n【A股专用外脑记忆库】：\n{rules_text}" if rules_text else "\n\n(当前A股外脑为空)"
            
            p_val = price if price else "未知"
            
            improved_prompt = f"""
            你是一位顶级的A股量化基金经理。请对标的 {target}（最新价 ¥{p_val}）出具一份【极度详尽、深度穿透】的A股量化研报。
            
            【硬性要求】：
            1. 字数不少于 1200 字
            2. 必须从以下四大维度深度拆解：
               - 核心基本面：上市公司主业逻辑、护城河、产业周期位置
               - 大面情绪共振：当前风格（价值/成长/周期），该股是否错杀或高估
               - 技术面断层：沪深两市支撑位、阻力位、筹码分布
               - 量化操作指令：明确的买入/卖出/加仓信号，精确止损止盈
            
            3. 针对A股特有因素：
               - 北向资金关注度（QFII、陆港通）
               - 融资融券余额是否异常
               - 主力是否在洗盘还是建仓
               - 最近龙虎榜有没有知名游资进场
            
            【外脑调用】：
            {sys_inject}
            """
            
            st.markdown("### 📋 A股专用深度研报")
            call_deepseek_stream(improved_prompt, system_role="作为顶级A股量化基金经理，你对沪深市场的政策、主力、散户心理了如指掌。请给出无懈可击的分析。")

        if btn_whale:
            with st.spinner("正在调动高阶算力，穿透明星机构底牌与交易异动..."):
                hist_5d = get_historical_data(target, 
                    (datetime.datetime.now() - datetime.timedelta(days=10)).strftime('%Y-%m-%d'), 
                    datetime.datetime.now().strftime('%Y-%m-%d'))
                
                volume_data = "近期无数据"
                if not hist_5d.empty:
                    recent_data = hist_5d[['Close', 'Volume']].tail(5)
                    volume_data = recent_data.to_string()
                
                p_val = price if price else "未知"
                
                whale_prompt = f"""
                你现在是陆家嘴最顶级的"巨鲸资金流向嗅探犬"。
                标的：{target}。当前价：¥{p_val}。
                
                请执行【宏观机构与微观盘口双重穿透】：
                
                第一部分：【宏观机构底牌深挖】
                - 该标的通常受哪些"5A 级基金经理"、"国家队/社保/养老"或"顶级游资（赵笑云、林园等）"的青睐？
                - 近期有没有新的大基金申报或清仓迹象？
                - 北向资金（陆港通）是在小幅建仓还是大幅净卖出？
                
                第二部分：【微观盘口解剖】
                最近 5 个交易日的量价数据：
                {volume_data}
                
                分析：
                - 是否存在放量滞涨（主力派发）或缩量下跌（主力恐慌）？
                - 龙虎榜有没有游资进场？
                
                第三部分：【巨鲸追踪结论】
                给出冷血的跟庄或避险建议。
                """
                
                st.markdown("### 🐳 巨鲸资金嗅探（A股版）")
                call_deepseek_stream(whale_prompt, system_role="你是一台拥有全A股视野、没有感情的盘口与机构解剖机器。你掌握龙虎榜、融资余额、基金持仓的一切数据。")

    # ==========================================
    # 4. 全局指挥部 (主界面)
    # ==========================================
    st.title("机构级资产指挥台 V21 (超级引擎·无限Token)")
    
    top_c1, top_c2 = st.columns([3, 1])
    with top_c1: 
        raw_target = st.text_input("🎯 锁定目标 (NVDA、TSLA、600459、000858 等)", "LITE", label_visibility="collapsed").upper().strip()
        
        target = raw_target
        market_badge = "🇺🇸 美股/其他"
        is_us_market = True
        
        if raw_target.isdigit() and len(raw_target) == 6:
            is_us_market = False
            if raw_target.startswith('6'):
                target = f"{raw_target}.SS"
                market_badge = "🇨🇳 A股 (沪)"
            elif raw_target.startswith(('0', '3')):
                target = f"{raw_target}.SZ"
                market_badge = "🇨🇳 A股 (深)"
        else:
            is_us_market = True

    with top_c2:
        price = get_current_price(target)
        if price:
            p_display = f"¥ {price}" if "🇨🇳" in market_badge else f"$ {price}"
            st.metric(f"📡 卫星报价 ({market_badge})", p_display)
        else:
            st.metric(f"📡 信号丢失 ({market_badge})", "未查找到该标的")

    st.markdown("---")

    # Token 使用情况显示
    col_status1, col_status2, col_status3 = st.columns(3)
    with col_status1:
        st.markdown(f"<div class='token-counter'>📞 DeepSeek 调用次数: {st.session_state.token_usage['deepseek_calls']}</div>", unsafe_allow_html=True)
    with col_status2:
        st.markdown(f"<div class='token-counter'>💰 估计消耗 Token: {st.session_state.token_usage['estimated_tokens']:,}</div>", unsafe_allow_html=True)
    with col_status3:
        if st.button("🔄 重置计数器"):
            st.session_state.token_usage['deepseek_calls'] = 0
            st.session_state.token_usage['estimated_tokens'] = 0
            st.rerun()

    st.markdown("---")

    tab_risk, tab_rl, tab_main, tab_brain, tab_extra = st.tabs([
        "🛡️ 天眼风控 (排雷)", 
        "⏳ 炼丹炉 (强化学习)", 
        "📈 量化推演 (主干-双引擎)", 
        "☁️ 云端外脑 (数据中心)",
        "⚡ 超级函数库"
    ])

    # ------------------------------------------
    # 模块 A：天眼风控
    # ------------------------------------------
    with tab_risk:
        st.markdown(f"### 🛡️ 极高权限合规审计：{target}")
        st.info("消耗算力扫描内幕交易、消息抢跑、监管问询等非财务治理风险��")
        
        if st.button("🚨 启动全网舆情风控网", key="btn_risk"):
            with st.spinner("正在渗透舆情数据源..."):
                try:
                    news_data = yf.Ticker(target).news
                    headlines = [n['title'] for n in news_data][:6] if news_data else "暂无强关联舆情"
                    
                    risk_prompt = f"""
                    你现在是 SEC 和中国证监会的顶级稽查员。标的：{target}。
                    最新接口抓取到的舆情线索：{headlines}。
                    请调动全网知识库，排查：
                    1. 该标的历史上是否存在'公告前股价提前异动'或'利好出尽暴跌'的劣迹？
                    2. 是否收到过监管关注函、问询函或遭到知名机构做空？
                    3. 若存在严重的信息违规或治理风险，请在开头用【一票否决】做出严厉警告并说明原因。
                    """
                    st.markdown("<div class='risk-alert'>正在执行深度排雷协议，请留意红色警告...</div>", unsafe_allow_html=True)
                    call_deepseek_stream(risk_prompt, system_role="作为无情的金融监管稽查机器，你的任务是找出标的背后的法律与治理暗雷。")
                except:
                    st.error("舆情接口抓取受限。")

    # ------------------------------------------
    # 模块 B：炼丹炉
    # ------------------------------------------
    with tab_rl:
        st.markdown(f"### ⏳ 强化学习时光机：{target}")
        st.caption("截断历史数据让AI盲猜，用未来数据打脸，逼迫其生成量化纪律，永久写入系统外脑。")
        
        col1, col2 = st.columns(2)
        with col1: start_d = st.date_input("盲测起点", datetime.date(2023, 1, 1), key="rl_start")
        with col2: end_d = st.date_input("盲测终点(截断点)", datetime.date(2023, 6, 1), key="rl_end")

        if st.button("🔥 启动闭门军演", key="btn_rl"):
            with st.spinner("正在切割历史时间线..."):
                s_str = start_d.strftime('%Y-%m-%d')
                e_str = end_d.strftime('%Y-%m-%d')
                
                hist = get_historical_data(target, s_str, e_str)
                
                if hist.empty:
                    st.warning("⚠️ 该时间段无数据。")
                else:
                    start_p = round(hist['Close'].iloc[0], 2)
                    end_p = round(hist['Close'].iloc[-1], 2)
                    
                    future_d = end_d + datetime.timedelta(days=30)
                    f_str = future_d.strftime('%Y-%m-%d')
                    future = get_historical_data(target, e_str, f_str)
                    future_p = round(future['Close'].iloc[-1], 2) if not future.empty else "未知"
                    
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
                    
                    if st.session_state.ds_key:
                        try:
                            res = call_deepseek_non_stream(rl_prompt + "请只输出最后那条40字以内的纪律本身，不要其他解释。")
                            if res:
                                market_tag = "🇨🇳" if not is_us_market else "🇺🇸"
                                insert_cloud_memory("reflection", f"【时光机验证 - {target}】{market_tag}: {res}")
                                st.success(f"✅ 思想钢印已自动写入云端数据库：{res}")
                        except Exception as e: st.error(f"云端记录失败: {e}")

    # ------------------------------------------
    # 模块 C：主干量化推演 - 双引擎版
    # ------------------------------------------
    with tab_main:
        st.markdown(f"### 📈 实时穿透：{target} ({market_badge})")
        
        if is_us_market:
            st.markdown("""
            <div class="us-card">
            <h4>🇺🇸 华尔街机构级分析系统</h4>
            <p>基于 MACD、RSI、期权 IV Skew、机构持仓等华尔街操盘手核心指标</p>
            </div>
            """, unsafe_allow_html=True)
            
            display_us_stock_analysis(target, price)
            
            # 美股额外功能：AI 分析
            if st.button("💡 启动 AI 华尔街策略顾问（深度模式）", use_container_width=True, key="btn_us_ai"):
                with st.spinner("正在连接华尔街数据库..."):
                    db = load_cloud_knowledge()
                    us_rules = [r for r in (db["strategies"] + db["reflections"]) if "🇺🇸" in r or "美股" in r]
                    us_inject = "\n".join(us_rules) if us_rules else "(美股外脑为空)"
                    
                    us_prompt = f"""
                    你是一位在美国华尔街工作 25 年的老牌对冲基金经理，管理资产超过 50 亿美金。
                    客户问你：{target}（当前价 ${price}）现在该不该买？三个月内目标价是多少？
                    
                    请基于以下维度给出冷酷、精确的交易建议（不少于 800 字）：
                    
                    1. 【技术面深度分析】
                       - MACD、RSI 当前状态
                       - 支撑位、阻力位在哪里
                       - 近期是否形成了有效的头肩形态或双底
                    
                    2. 【期权市场深度解读】
                       - IV Skew 透露出什么信息
                       - 关键行权价附近的成交活跃度
                       - 机构是在防守还是在进攻
                    
                    3. 【基本面与估值】
                       - P/E、P/S、PEG 在行业���处于什么位置
                       - 最近一个季度的盈利增速
                       - 管理层最近的业绩指引
                    
                    4. 【宏观风险与黑天鹅】
                       - 美联储政策走向对该股的影响
                       - 行业是否面临政策风险（如科技股的反垄断）
                       - 地缘政治风险
                    
                    5. 【机构动向】
                       - 近期有没有知名基金增仓或减仓
                       - 内部人（CEO、CFO）是否在买进或卖出
                    
                    6. 【具体操作指令】
                       - 如果我现在买入，应该在哪个价位
                       - 止损应该设在多少
                       - 三个月目标价是多少
                       - 风险收益比多少才值得操作
                    
                    参考的历史美股纪律库：
                    {us_inject}
                    
                    你的答案需要非常专业、冷酷、有执行力，不要任何废话或情绪化分析。
                    """
                    
                    st.markdown("### 🎯 华尔街 25 年资深操盘手的冷血建议")
                    call_deepseek_stream(us_prompt, system_role="你是一位在华尔街打了 25 年的资深对冲基金经理。你的分析必须精确、冷酷、没有任何感情。每一个观点都要基于数据和历史回溯。")
        
        else:
            st.markdown("""
            <div class="cn-card">
            <h4>🇨🇳 A股专业机构分析系统</h4>
            <p>基于盘口解剖、龙虎榜、融资融券、基金持仓等沪深市场核心逻辑</p>
            </div>
            """, unsafe_allow_html=True)
            
            display_cn_stock_analysis(target, price)

    # ------------------------------------------
    # 模块 D：云端外脑
    # ------------------------------------------
    with tab_brain:
        st.markdown("### ☁️ 云端 RAG 向量记忆中心 (Supabase驱动)")
        st.caption("支持手动喂养，或直接上传 PDF/Word/PPT 研报，AI将自动榨取战法并永久保存。")
        
        c_feed1, c_feed2 = st.columns([1, 1])
        
        with c_feed1:
            st.markdown("**📝 1. 碎片战法投喂 (纯文本)**")
            feed_text = st.text_area("粘贴聊天记录或大白话", placeholder="例如：MACD 金叉 + RSI < 30 是美股黄金买点... 或 CPO板块连续三天缩量阴跌后第四天早盘急杀可捞底...", key="feed_text")
            if st.button("🧠 提炼文本并刻入云端", key="btn_text_feed"):
                if feed_text and st.session_state.ds_key:
                    with st.spinner("正在提炼规则并连接数据库..."):
                        res = call_deepseek_non_stream(f"将以下内容转化为一条极其精简、冷酷的量化纪律(不超过50字)，并标注市场标签（A股用🇨🇳，美股用🇺🇸）：{feed_text}")
                        if res:
                            insert_cloud_memory("strategy", f"【手动植入】: {res}")
                            st.success("✅ 战法已永久写入云端底层！")
                            time.sleep(1)
                            st.rerun()
                elif not st.session_state.ds_key: st.error("缺少 API Key。")

        with c_feed2:
            st.markdown("**📂 2. 机构研报/课件投喂**")
            uploaded_file = st.file_uploader("支持 .pdf, .docx, .pptx, .txt 格式", type=['pdf', 'docx', 'pptx', 'txt'])
            
            if st.button("🧬 启动文档深度榨取", key="btn_doc_feed"):
                if uploaded_file is not None and st.session_state.ds_key:
                    with st.spinner("正在强行破译文档排版，提取底层文字..."):
                        extracted_text = ""
                        try:
                            if uploaded_file.name.endswith('.pdf'):
                                import PyPDF2
                                pdf_reader = PyPDF2.PdfReader(uploaded_file)
                                for page in pdf_reader.pages:
                                    text = page.extract_text()
                                    if text: extracted_text += text + "\n"
                            elif uploaded_file.name.endswith('.docx'):
                                import docx
                                doc = docx.Document(uploaded_file)
                                extracted_text = "\n".join([p.text for p in doc.paragraphs if p.text])
                            elif uploaded_file.name.endswith('.pptx'):
                                import pptx
                                ppt = pptx.Presentation(uploaded_file)
                                for slide in ppt.slides:
                                    for shape in slide.shapes:
                                        if hasattr(shape, "text"):
                                            extracted_text += shape.text + "\n"
                            elif uploaded_file.name.endswith('.txt'):
                                extracted_text = uploaded_file.getvalue().decode("utf-8")
                                
                            if not extracted_text.strip():
                                st.warning("文档似乎是空的或全是图片，无法提取文字。")
                            else:
                                st.info(f"成功提取 {len(extracted_text)} 字情报，正在呼叫 DeepSeek 进行降维打击...")
                                safe_text = extracted_text[:20000] 
                                
                                prompt = f"""
                                你是一个冷酷的量化策略提取器。请从以下文档中，榨取出最核心的、带有触发条件的【量化纪律/交易规则】。
                                要求：
                                1. 提炼为 3-6 条最硬核的规则。
                                2. 每条严格控制在 50 字以内。
                                3. 每条规则末尾加上市场标签：(A股) 或 (美股) 或 (通用)
                                4. 不要任何废话，直接按行输出结果。
                                文档内容：{safe_text}
                                """
                                res = call_deepseek_non_stream(prompt, max_tokens=2000)
                                
                                if res:
                                    new_rules = [r.strip() for r in res.split('\n') if r.strip() and len(r)>5]
                                    for rule in new_rules:
                                        insert_cloud_memory("strategy", f"【研报-{uploaded_file.name[:10]}】: {rule}")
                                    
                                    st.success(f"✅ 成功榨取并写入 {len(new_rules)} 条硬核战法至云端！")
                                    time.sleep(1.5)
                                    st.rerun()

                        except Exception as e:
                            st.error(f"文档解析或云端传输失败: {e}")
                elif not st.session_state.ds_key: st.error("缺少 API Key。")
                else: st.warning("请先上传文件！")
        
        st.markdown("---")
        st.markdown("**🗑️ 外脑记忆管理中心**")
        
        all_records = get_all_cloud_memories()
        
        if all_records:
            options_dict = {record['id']: record['content'] for record in all_records}
            selected_ids = st.multiselect(
                "请选择需要从云端剔除的过期纪律：",
                options=list(options_dict.keys()),
                format_func=lambda x: options_dict[x],
                placeholder="点击下拉框查看并圈选..."
            )
            
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

    # ------------------------------------------
    # 模块 E：超级函数库 (V21.1 灵魂注入补丁版)
    # ------------------------------------------
    with tab_extra:
        st.markdown("### ⚡ 超级函数库 (已注入云端外脑 + 财务真数据)")
        
        # --- 统一的前置逻辑：获取当前市场的云端外脑 ---
        def get_scoped_knowledge():
            db = load_cloud_knowledge()
            all_rules = db["strategies"] + db["reflections"]
            # 过滤当前市场标签
            scoped_rules = [r for r in all_rules if (is_us_market and "🇺🇸" in r) or (not is_us_market and "🇨🇳" in r) or ("通用" in r)]
            return "\n".join(scoped_rules) if scoped_rules else "暂无匹配纪律"

        st.info("已完成数据隔离与纪律注入。每次分析将消耗约 4000-6000 Tokens。")
        
        # 1. 行业对标分析
        if st.button("📊 行业对标深度分析", use_container_width=True, key="btn_industry_v2"):
            with st.spinner("正在对比行业矩阵..."):
                rules = get_scoped_knowledge()
                prompt = f"分析 {target} 行业地位。请务必结合以下【系统外脑纪律】进行价值判定：\n{rules}\n\n分析维度：行业地位、估值对标、增速、盈利能力、投资结论。"
                call_deepseek_stream(prompt, system_role="资深行业分析师")

        # 2. 基金持仓追踪
        if st.button("🏛️ 基金持仓与机构博弈", use_container_width=True, key="btn_fund_v2"):
            with st.spinner("正在追踪大资金动向..."):
                rules = get_scoped_knowledge()
                prompt = f"分析 {target} 的明星基金持仓与机构博弈。结合以下【外脑纪律】判定机构行为：\n{rules}\n\n分析维度：明星基金、增减仓动向、北向/机构占比、跟仓建议。"
                call_deepseek_stream(prompt, system_role="基金研究专家")

        # 3. 目标价预测 (✨核心修复：喂入真实财务数据防止幻觉)
        if st.button("🎯 多周期目标价预测 (基于真数据)", use_container_width=True, key="btn_target_v2"):
            with st.spinner("正在调取财务报表并进行 DCF 建模..."):
                # 强行抓取真实财务摘要
                stock_obj = yf.Ticker(target)
                info = stock_obj.info
                financials = stock_obj.financials.iloc[:, :2].to_string() # 最近两年的利润表
                
                rules = get_scoped_knowledge()
                target_prompt = f"""
                你是一位投行估值专家。基于以下【真实财务数据】和【系统纪律】进行建模。
                
                【真实数据摘要】：
                市值: {info.get('marketCap')} | P/E: {info.get('trailingPE')} | 营收增长: {info.get('revenueGrowth')}
                最近财报数据：
                {financials}
                
                【系统外脑纪律】：
                {rules}
                
                指令：使用 DCF 和相对估值法，给出 3/6/12 个月精确目标价。严禁伪造财务数字！
                """
                call_deepseek_stream(target_prompt, system_role="投行估值专家")

        # 4. 深度风险预警
        if st.button("⚠️ 深度风险预警 (偏执模式)", use_container_width=True, key="btn_risk_v2"):
            with st.spinner("正在扫描黑天鹅..."):
                rules = get_scoped_knowledge()
                prompt = f"对 {target} 进行全维度风险扫描。结合【外脑纪律】中的避险准则：\n{rules}\n\n维度：财务、业务、政策、市场黑天鹅。给出最后风险等级 L1-L5。"
                call_deepseek_stream(prompt, system_role="极度偏执的风险管理专家")

        # 5. 最新财报解读 (✨核心修复：喂入最新季报数据)
        if st.button("📈 最新季度财报深度解剖", use_container_width=True, key="btn_earnings_v2"):
            with st.spinner("正在拆解最新季报文字与数字..."):
                stock_obj = yf.Ticker(target)
                quarterly_results = stock_obj.quarterly_financials.iloc[:, :1].to_string() # 最新一季报数据
                
                rules = get_scoped_knowledge()
                earnings_prompt = f"""
                你是一位财务审计专家。请拆解 {target} 的最新季度财报。
                
                【本季真实数字】：
                {quarterly_results}
                
                【系统外脑纪律】：
                {rules}
                
                指令：分析收入/利润质量、现金流健康度、管理层指引。判断是基本面反转还是陷阱。
                """
                call_deepseek_stream(earnings_prompt, system_role="财务审计专家")
