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
st.set_page_config(page_title="量化交易终端 V20.0 云端版 (双引擎)", page_icon="🦈", layout="wide")

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
    st.markdown("<h1 style='text-align: center; margin-top: 10vh;'>Terminal V20 (Cloud · 双引擎)</h1>", unsafe_allow_html=True)
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
        st.error(f"⚠️ 云端配置缺失，��检查 Secrets。详细报错: {e}")

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
    # ✨✨✨ 新增：华尔街美股专用引擎 ✨✨✨
    # ==========================================
    
    # 美股 1：MACD + RSI 机构信号
    @st.cache_data(ttl=600)
    def compute_us_tech_signals(ticker):
        """华尔街机构常用的两大金融指标"""
        try:
            hist = get_historical_data(ticker, 
                (datetime.datetime.now() - datetime.timedelta(days=252)).strftime('%Y-%m-%d'),
                datetime.datetime.now().strftime('%Y-%m-%d'))
            
            if hist.empty or len(hist) < 26:
                return None
            
            # RSI-14
            delta = hist['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            
            # MACD
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

    # 美股 2：期权市场隐含波动率（机构真实意图）
    @st.cache_data(ttl=1800)
    def fetch_us_options_signal(ticker):
        """从期权市场反推机构对股票的定价与情绪"""
        try:
            stock = yf.Ticker(ticker)
            expirations = stock.options
            
            if not expirations:
                return None
            
            # 抓最近的一个月合约
            exp_date = expirations[0]
            opt = stock.option_chain(exp_date)
            calls = opt.calls
            puts = opt.puts
            
            # 计算平均 IV
            call_iv_mean = calls['impliedVolatility'].mean() if not calls.empty else 0
            put_iv_mean = puts['impliedVolatility'].mean() if not puts.empty else 0
            
            # IV Skew = Put IV - Call IV（极值警告）
            iv_skew = round((put_iv_mean - call_iv_mean) * 100, 1) if call_iv_mean > 0 else 0
            
            # 找主力关注的执行价
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

    # 美股 3：机构持仓占比
    @st.cache_data(ttl=3600)
    def fetch_us_institutional_data(ticker):
        """追踪机构与内部人持仓比例"""
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

    # 美股展示 UI
    def display_us_stock_analysis(target, price):
        """完整的美股华尔街分析界面"""
        st.markdown("#### 🇺🇸 华尔街机构三层穿透系统")
        
        # 第一层：技术面（MACD + RSI）
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
                st.metric("📈 Signal Line", signals['signal'], "")
            
            with col4:
                macd_color = "🟢" if signals['histogram'] > 0 else "🔴"
                st.metric(f"{macd_color} Histogram", signals['histogram'], signals['macd_status'])
            
            # MACD 策略建议
            if signals['macd_status'] == 'BULLISH_CROSS':
                st.success("✅ **金叉信号激活**：短期看多，华尔街操盘手常在此建仓")
            elif signals['macd_status'] == 'BEARISH_CROSS':
                st.error("❌ **死叉信号激活**：短期看空，风险示警")
            elif signals['macd_status'] == 'STRONG_BULL':
                st.info("💪 **多头强势**：MACD 在 0 线之上且直方图向上")
            else:
                st.warning("⚠️ **空头强势**：MACD 在 0 线之下且直方图向下")
        else:
            st.warning("无法获取该股票的技术面数据（数据不足或退市）")
        
        st.markdown("---")
        
        # 第二层：期权市场（IV Skew）
        st.markdown("**第二层：期权市场隐含信号（机构真实意图）**")
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
                st.metric(f"📍 关键行权价", f"${opt_signal['key_strike']}", f"vs 当前 ${current}")
            
            st.info(f"💡 期权到期日：{opt_signal['expiration']} | 总持仓量：{opt_signal['total_open_interest']:,}")
        else:
            st.warning("该股票期权数据不可用（可能是小市值股或新股）")
        
        st.markdown("---")
        
        # 第三层：机构持仓战争
        st.markdown("**第三层：机构持仓战争（谁在控盘）**")
        inst_data = fetch_us_institutional_data(target)
        
        if inst_data:
            col_inst1, col_inst2 = st.columns(2)
            
            with col_inst1:
                if inst_data['inst_pct']:
                    if inst_data['inst_pct'] > 60:
                        st.success(f"✅ 机构重兵布防：{inst_data['inst_pct']}%")
                    elif inst_data['inst_pct'] > 40:
                        st.info(f"🟡 机构主流持仓：{inst_data['inst_pct']}%")
                    else:
                        st.warning(f"⚠️ 机构撤离迹象：{inst_data['inst_pct']}%")
            
            with col_inst2:
                if inst_data['insider_pct']:
                    if inst_data['insider_pct'] > 20:
                        st.success(f"✅ 内部人看好（管理层增持）：{inst_data['insider_pct']}%")
                    else:
                        st.caption(f"内部人持仓：{inst_data['insider_pct']}%")
        else:
            st.info("机构持仓数据暂不可用")
        
        st.markdown("---")

    # ==========================================
    # ✨✨✨ A股独立引擎保持原逻辑 ✨✨✨
    # ==========================================

    def display_cn_stock_analysis(target, price):
        """A股深度量化研报 + 巨鲸追踪"""
        
        col_cn1, col_cn2 = st.columns(2)
        
        with col_cn1:
            btn_deepseek = st.button("🚀 启动外脑深度推演（A股专用）", use_container_width=True, key="btn_cn_deepseek")
        
        with col_cn2:
            btn_whale = st.button("🐳 巨鲸资金嗅探", type="primary", use_container_width=True, key="btn_cn_whale")
        
        # A股逻辑 1：外脑推演
        if btn_deepseek:
            with st.spinner("正在从云端调取适配当前市场的量化纪律..."):
                db = load_cloud_knowledge() 
                all_rules = db["strategies"] + db["reflections"]
                
                filtered_rules = [r for r in all_rules if "🇨🇳" in r or "A股" in r or "沪深" in r]
                rules_text = "\n".join(filtered_rules)
                sys_inject = f"\n\n【A股专用外脑记忆库】：\n{rules_text}" if rules_text else "\n\n(当前A股外脑为空，建议喂养数据)"
            
            p_val = price if price else "未知"
            
            improved_prompt = f"""
            你是一位顶级的A股量化基金经理。请对标的 {target}（最新价 ¥{p_val}）出具一份【极度详尽、深度穿透】的A股量化研报。
            
            【硬性要求】：
            1. 字数不少于 800 字
            2. 必须从以下四大维度深度拆解：
               - 核心基本面：上市公司主业逻辑、护城河、产业周期位置
               - 大面情绪共振：结合当前大盘风格（价值/成长/周期），该股是否错杀或高估
               - 技术面断层：沪深两市的支撑位、阻力位、筹码分布
               - 量化操作指令：明确的买入/卖出/加仓信号，精确到小数点的止损止盈位
            
            3. 针对A股特有因素：
               - 是否有北向资金关注（QFII、陆港通）
               - 融资融券余额是否异常
               - 主力是否在洗盘还是建仓
            
            【外脑调用】：
            下方是来自历史积累的【A股专用外脑记忆库】。请智能应用那些与本标的核心业务相关的纪律。
            {sys_inject}
            """
            
            st.markdown("### 📋 A股专用深度研报")
            call_deepseek_stream(improved_prompt, system_role="作为顶级A股量化基金经理，你对沪深市场的政策、主力、散户心理了如指掌。")

        # A股逻辑 2：巨鲸追踪
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
                - 该标的通常受哪些"5A 级基金经理"、"国家队/社保/养老"或"顶级游资（如赵笑云、林园）"的青睐？
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
                call_deepseek_stream(whale_prompt, system_role="作为一台拥有全A股视野、没有感情的盘口与机构解剖机器，你掌握龙虎榜、融资余额、基金持仓的一切数据。")

    # ==========================================
    # 4. 全局指挥部 (主界面) - V20.0 双引擎版
    # ==========================================
    st.title("机构级资产指挥台 (双引擎：华尔街 + 陆家嘴)")
    
    top_c1, top_c2 = st.columns([3, 1])
    with top_c1: 
        raw_target = st.text_input("🎯 锁定目标 (支持纯数字如 600459、000858，或美股 NVDA、TSLA)", "LITE", label_visibility="collapsed").upper().strip()
        
        # ✨ 智能后缀补全引擎
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

    tab_risk, tab_rl, tab_main, tab_brain = st.tabs([
        "🛡️ 天眼风控 (排雷)", 
        "⏳ 炼丹炉 (强化学习)", 
        "📈 量化推演 (主干-双引擎)", 
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
    # 模块 B：炼丹炉 (强化学习与纪律提取)
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
                            
                            market_tag = "🇨🇳" if not is_us_market else "🇺🇸"
                            insert_cloud_memory("reflection", f"【时光机验证 - {target}】{market_tag}: {res}")
                            st.success(f"✅ 思想钢印已自动写入云端数据库：{res}")
                        except Exception as e: st.error(f"云端记录失败: {e}")

    # ------------------------------------------
    # 模块 C：主干量化推演 - 双引擎版 (核心改造)
    # ------------------------------------------
    with tab_main:
        st.markdown(f"### 📈 实时穿透：{target} ({market_badge})")
        
        if is_us_market:
            # ✨✨✨ 美股独立体系 ✨✨✨
            st.markdown("""
            <div class="us-card">
            <h4>🇺🇸 华尔街机构级分析系统</h4>
            <p>基于 MACD、RSI、期权 IV Skew、机构持仓等华尔街操盘手核心指标</p>
            </div>
            """, unsafe_allow_html=True)
            
            display_us_stock_analysis(target, price)
            
            # 美股额外功能：AI 分析
            if st.button("💡 启动 AI 华尔街策略顾问", use_container_width=True, key="btn_us_ai"):
                with st.spinner("正在连接华尔街数据库..."):
                    db = load_cloud_knowledge()
                    us_rules = [r for r in (db["strategies"] + db["reflections"]) if "🇺🇸" in r or "美股" in r]
                    us_inject = "\n".join(us_rules) if us_rules else "(美股外脑为空)"
                    
                    us_prompt = f"""
                    你是一位在美国华尔街工作 20 年的老牌量化交易员。
                    客户问你：{target}（当前价 ${price}）现在该不该买？
                    
                    请基于以下维度给出冷酷、精确的交易建议（不超过 500 字）：
                    1. 技术面：根据 MACD、RSI 的信号
                    2. 期权市场：根据 IV Skew 和关键行权价
                    3. 机构动向：根据持仓占比变化
                    4. 风险等级：明确标注风险等级 (L1-L5)
                    5. 操作建议：买/持/卖，以及具体的入场价、止损价、目标价
                    
                    参考的历史美股纪律：
                    {us_inject}
                    """
                    
                    st.markdown("### 🎯 华尔街老兵的冷血建议")
                    call_deepseek_stream(us_prompt, system_role="你是一位在华尔街打了 20 年的机构交易员，对标普 500、纳斯达克的每一支明星股都有深刻的理解。")
        
        else:
            # ✨✨✨ A股独立体系 ✨✨✨
            st.markdown("""
            <div class="cn-card">
            <h4>🇨🇳 A股专业机构分析系统</h4>
            <p>基于盘口解剖、龙虎榜、融资融券、基金持仓等沪深市场核心逻辑</p>
            </div>
            """, unsafe_allow_html=True)
            
            display_cn_stock_analysis(target, price)

    # ------------------------------------------
    # ���块 D：策略外脑数据中心
    # ------------------------------------------
    with tab_brain:
        st.markdown("### ☁️ 云端 RAG 向量记忆中心 (Supabase驱动)")
        st.caption("支持手动喂养，或直接上传 PDF/Word/PPT 研报，AI将自动榨取战法并永久保存。")
        
        c_feed1, c_feed2 = st.columns([1, 1])
        
        # --- 方式 1：手动文本投喂 ---
        with c_feed1:
            st.markdown("**📝 1. 碎片战法投喂 (纯文本)**")
            feed_text = st.text_area("粘贴聊天记录或大白话", placeholder="例如：CPO板块连续三天缩量阴跌后，第四天早盘急杀可捞底（A股）或 MACD 金叉 + RSI < 30 是美股的黄金买点...", key="feed_text")
            if st.button("🧠 提炼文本并刻入云端", key="btn_text_feed"):
                if feed_text and st.session_state.ds_key:
                    with st.spinner("正在提炼规则并连接数据库..."):
                        client = OpenAI(api_key=st.session_state.ds_key, base_url="https://api.deepseek.com/v1")
                        res = client.chat.completions.create(
                            model="deepseek-chat", 
                            messages=[{"role": "user", "content": f"将以下内容转化为一条极其精简、冷酷的量化纪律(不超过50字)，并标注市场标签（A股用🇨🇳，美股用🇺🇸）：{feed_text}"}]
                        ).choices[0].message.content
                        
                        insert_cloud_memory("strategy", f"【手动植��】: {res}")
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
                                你是一个冷酷的量化策略提取器。请从以下文档中，榨取出最核心的、带有触发条件的【量化纪律/交易规则】。
                                要求：
                                1. 提炼为 2-4 条最硬核的规则。
                                2. 每条严格控制在 50 字以内。
                                3. 每条规则末尾加上市场标签：(A股) 或 (美股) 或 (通用)
                                4. 不要任何废话，直接按行输出结果。
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
            # 构建一个字典，把记录的 ID 映射到它的具体内容上
            options_dict = {record['id']: record['content'] for record in all_records}
            
            # 圈选多选框
            selected_ids = st.multiselect(
                "请选择需要从云端剔除的过期纪律：",
                options=list(options_dict.keys()),
                format_func=lambda x: options_dict[x],
                placeholder="点击下拉框查看并圈选..."
            )
            
            # 删除按钮
            if st.button("🔥 彻���抹除选中的记忆", type="primary"):
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
