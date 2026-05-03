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
st.set_page_config(page_title="量化交易终端 V22.0 全球三市场版", page_icon="🦈", layout="wide")

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
    .hk-card { background-color: #FFE5F0; padding: 15px; border-radius: 8px; border-left: 4px solid #D91E63; margin-bottom: 10px; }
    .jp-card { background-color: #FFF0E5; padding: 15px; border-radius: 8px; border-left: 4px solid #FF6B35; margin-bottom: 10px; }
    .cn-card { background-color: #FFF8F0; padding: 15px; border-radius: 8px; border-left: 4px solid #FF6B35; margin-bottom: 10px; }
    .token-counter { background-color: #FFE5E5; padding: 10px; border-radius: 8px; font-size: 0.85rem; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 📊 Token 消耗计数器
# ==========================================
if 'token_usage' not in st.session_state:
    st.session_state.token_usage = {
        'deepseek_calls': 0,
        'estimated_tokens': 0
    }

def log_token_usage(prompt_tokens_estimate=2000, completion_tokens_estimate=1500):
    st.session_state.token_usage['deepseek_calls'] += 1
    st.session_state.token_usage['estimated_tokens'] += (prompt_tokens_estimate + completion_tokens_estimate)

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
        return st.error("❌ 缺少 DeepSeek 密钥")
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
        st.error(f"⚠️ DeepSeek 调用失败: {e}")

def call_deepseek_non_stream(prompt, system_role="作为顶级量化基金经理。", max_tokens=2000):
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
# ✨ 多交易所智能识别引擎 ✨
# ==========================================

def identify_market(raw_input):
    """智能识别输入符号属于哪个交易所"""
    raw_input = raw_input.upper().strip()
    
    # A 股判断（纯数字）
    if raw_input.isdigit() and len(raw_input) == 6:
        if raw_input.startswith('6'):
            return f"{raw_input}.SS", "A_SHARE_SH", "🇨🇳 A股 (沪)", "¥"
        elif raw_input.startswith(('0', '3')):
            return f"{raw_input}.SZ", "A_SHARE_SZ", "🇨🇳 A股 (深)", "¥"
    
    # 港股判断（以 0 开头的 4 位数字）
    if raw_input.isdigit() and len(raw_input) == 4 and raw_input.startswith('0'):
        return f"{raw_input}.HK", "HK_STOCK", "🇭🇰 港股 (HK)", "HK$"
    elif raw_input.endswith('.HK'):
        return raw_input, "HK_STOCK", "🇭🇰 港股 (HK)", "HK$"
    
    # 日股判断（以 6 开头的 4 位数字）
    if raw_input.isdigit() and len(raw_input) == 4 and raw_input.startswith('6'):
        return f"{raw_input}.T", "JP_STOCK", "🇯🇵 日股 (JPX)", "¥"
    elif raw_input.endswith('.T'):
        return raw_input, "JP_STOCK", "🇯🇵 日股 (JPX)", "¥"
    
    # 美股判断（字母）
    if raw_input.isalpha() or '.' in raw_input:
        return raw_input, "US_STOCK", "🇺🇸 美股 (NASDAQ/NYSE)", "$"
    
    # 默认美股
    return raw_input, "US_STOCK", "🇺🇸 美股 (NASDAQ/NYSE)", "$"

# ==========================================
# 3. 权限认证与 Supabase 云端连线
# ==========================================
if 'user_role' not in st.session_state: 
    st.session_state.user_role = None

if st.session_state.user_role is None:
    st.markdown("<h1 style='text-align: center; margin-top: 10vh;'>Terminal V22 (全球三市场)</h1>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        pwd = st.text_input("", type="password", placeholder="输入访问密钥", label_visibility="collapsed")
        if st.button("接入系统"):
            if pwd == "888888": st.session_state.user_role = "Admin"; st.rerun()
            elif pwd == "guest": st.session_state.user_role = "Guest"; st.rerun()
            else: st.error("密钥验证失败")
else:
    try:
        st.session_state.ds_key = st.secrets["DEEPSEEK_API_KEY"]
        sb_url = st.secrets["SUPABASE_URL"]
        sb_key = st.secrets["SUPABASE_KEY"]
        supabase: Client = create_client(sb_url, sb_key)
    except Exception as e:
        st.session_state.ds_key = None
        supabase = None
        st.error(f"⚠️ 云端配置缺失: {e}")

    def load_cloud_knowledge():
        if not supabase: return {"strategies": [], "reflections": []}
        try:
            res = supabase.table("brain_memory").select("*").execute()
            data = res.data
            return {
                "strategies": [d['content'] for d in data if d['memory_type'] == 'strategy'],
                "reflections": [d['content'] for d in data if d['memory_type'] == 'reflection']
            }
        except: return {"strategies": [], "reflections": []}

    def insert_cloud_memory(m_type, content):
        if not supabase: return
        try:
            supabase.table("brain_memory").insert({"memory_type": m_type, "content": content}).execute()
        except: pass

    def get_all_cloud_memories():
        if not supabase: return []
        try:
            res = supabase.table("brain_memory").select("id, memory_type, content").order("id", desc=True).execute()
            return res.data
        except: return []

    def delete_cloud_memories(ids_to_delete):
        if not supabase or not ids_to_delete: return
        try:
            supabase.table("brain_memory").delete().in_("id", ids_to_delete).execute()
        except: pass

    # ==========================================
    # ✨✨✨ A股专业数据补充（akshare）✨✨✨
    # ==========================================

    @st.cache_data(ttl=600)
    def get_cn_dragon_tiger_board(stock_code):
        """获取 A 股龙虎榜数据"""
        try:
            import akshare as ak
            df = ak.stock_lhb_detail_daily(symbol=stock_code)
            if df.empty:
                return None
            
            recent = df.head(10)
            return {
                'latest_date': recent.iloc[0]['trade_date'] if not recent.empty else None,
                'buy_seats': len(recent[recent['type'] == 'buy']) if not recent.empty else 0,
                'sell_seats': len(recent[recent['type'] == 'sell']) if not recent.empty else 0,
                'top_buyer': recent[recent['type'] == 'buy'].iloc[0]['name'] if len(recent[recent['type'] == 'buy']) > 0 else None,
            }
        except Exception as e:
            st.warning(f"龙虎榜获取失败: {e}")
            return None

    @st.cache_data(ttl=300)
    def get_cn_margin_data(stock_code):
        """获取 A 股融资融券数据"""
        try:
            import akshare as ak
            df = ak.stock_margin(symbol=stock_code)
            if df.empty:
                return None
            
            latest = df.iloc[-1]
            return {
                'financing_balance': latest.get('融资余额', 0),
                'short_balance': latest.get('融券余额', 0),
                'financing_ratio': latest.get('融资买入占比', 0),
            }
        except:
            return None

    @st.cache_data(ttl=3600)
    def get_cn_fund_holdings(stock_code):
        """获取 A 股基金持仓数据"""
        try:
            import akshare as ak
            df = ak.stock_fund_holdings(symbol=stock_code)
            if df.empty:
                return None
            
            return {
                'total_funds': len(df),
                'top_funds': df.head(3)['基金名称'].tolist() if len(df) > 0 else [],
            }
        except:
            return None

    @st.cache_data(ttl=300)
    def get_cn_north_bound_data():
        """获取北向资金实时数据"""
        try:
            import akshare as ak
            df = ak.bond_zh_hs_north_net_flow_in()
            if df.empty:
                return None
            
            latest = df.iloc[0]
            return {
                'date': latest.get('日期', ''),
                'net_flow': latest.get('北向资金（亿）', 0),
            }
        except:
            return None

    # ==========================================
    # 美股技术面分析
    # ==========================================
    
    @st.cache_data(ttl=600)
    def compute_us_tech_signals(ticker):
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
            latest_histogram = histogram.iloc[-1]
            
            return {
                'rsi': round(latest_rsi, 2),
                'macd': round(macd.iloc[-1], 4),
                'histogram': round(latest_histogram, 4),
                'rsi_status': 'OVERBOUGHT(>70)' if latest_rsi > 70 else ('OVERSOLD(<30)' if latest_rsi < 30 else 'NEUTRAL'),
                'macd_status': 'BULLISH' if latest_histogram > 0 else 'BEARISH',
            }
        except:
            return None

    @st.cache_data(ttl=1800)
    def fetch_us_options_signal(ticker):
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
                'call_iv': round(call_iv_mean, 3),
                'put_iv': round(put_iv_mean, 3),
                'iv_skew': iv_skew,
                'key_strike': round(key_strike, 2) if key_strike else None,
            }
        except:
            return None

    # ==========================================
    # 港股技术面分析
    # ==========================================
    
    @st.cache_data(ttl=600)
    def compute_hk_signals(ticker):
        try:
            hist = get_historical_data(ticker, 
                (datetime.datetime.now() - datetime.timedelta(days=120)).strftime('%Y-%m-%d'),
                datetime.datetime.now().strftime('%Y-%m-%d'))
            
            if hist.empty or len(hist) < 20:
                return None
            
            delta = hist['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            latest_rsi = rsi.iloc[-1]
            
            ma20 = hist['Close'].rolling(window=20).mean().iloc[-1]
            latest_close = hist['Close'].iloc[-1]
            
            return {
                'rsi': round(latest_rsi, 2),
                'ma20': round(ma20, 2),
                'latest_close': round(latest_close, 2),
                'trend': 'UPTREND' if latest_close > ma20 else 'DOWNTREND',
            }
        except:
            return None

    # ==========================================
    # 日股技术面分析
    # ==========================================
    
    @st.cache_data(ttl=600)
    def compute_jp_signals(ticker):
        try:
            hist = get_historical_data(ticker, 
                (datetime.datetime.now() - datetime.timedelta(days=120)).strftime('%Y-%m-%d'),
                datetime.datetime.now().strftime('%Y-%m-%d'))
            
            if hist.empty or len(hist) < 20:
                return None
            
            delta = hist['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            latest_rsi = rsi.iloc[-1]
            
            ma20 = hist['Close'].rolling(window=20).mean().iloc[-1]
            volatility = hist['Close'].pct_change().std() * 100
            
            return {
                'rsi': round(latest_rsi, 2),
                'ma20': round(ma20, 2),
                'volatility': round(volatility, 2),
                'trend': 'UPTREND' if hist['Close'].iloc[-1] > ma20 else 'DOWNTREND',
            }
        except:
            return None

    # ==========================================
    # UI 展示函数
    # ==========================================

    def display_us_stock_analysis(target, price):
        st.markdown("#### 🇺🇸 华尔街机构穿透系统")
        
        signals = compute_us_tech_signals(target)
        if signals:
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                rsi_color = "🔴" if signals['rsi'] > 70 else ("🟢" if signals['rsi'] < 30 else "🟡")
                st.metric(f"{rsi_color} RSI-14", signals['rsi'], signals['rsi_status'])
            with col2:
                st.metric("📊 MACD", signals['macd'], "")
            with col3:
                st.metric("📈 Histogram", signals['histogram'], "")
            with col4:
                st.metric("📊 Status", signals['macd_status'], "")
        
        opt_signal = fetch_us_options_signal(target)
        if opt_signal:
            st.info(f"期权 IV Skew: {opt_signal['iv_skew']}% | 关键行权价: ${opt_signal['key_strike']}")
        
        st.markdown("---")

    def display_hk_stock_analysis(target, price):
        st.markdown("#### 🇭🇰 港股深度分析系统")
        
        signals = compute_hk_signals(target)
        if signals:
            col1, col2, col3 = st.columns(3)
            with col1:
                rsi_color = "🔴" if signals['rsi'] > 70 else ("🟢" if signals['rsi'] < 30 else "🟡")
                st.metric(f"{rsi_color} RSI-14", signals['rsi'], "")
            with col2:
                st.metric("📊 MA20", f"HK${signals['ma20']}", "")
            with col3:
                trend_color = "🟢" if signals['trend'] == "UPTREND" else "🔴"
                st.metric(f"{trend_color} 趋势", signals['trend'], "")
        
        st.markdown("---")

    def display_jp_stock_analysis(target, price):
        st.markdown("#### 🇯🇵 日股深度分析系统")
        
        signals = compute_jp_signals(target)
        if signals:
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                rsi_color = "🔴" if signals['rsi'] > 70 else ("🟢" if signals['rsi'] < 30 else "🟡")
                st.metric(f"{rsi_color} RSI-14", signals['rsi'], "")
            with col2:
                st.metric("📊 MA20", f"¥{signals['ma20']}", "")
            with col3:
                st.metric("📈 波动率", f"{signals['volatility']}%", "")
            with col4:
                trend_color = "🟢" if signals['trend'] == "UPTREND" else "🔴"
                st.metric(f"{trend_color} 趋势", signals['trend'], "")
        
        st.markdown("---")

    def display_cn_stock_analysis(target, price):
        """A股深度分析 - 集成 akshare 专业数据"""
        
        # 提取 A 股代码（去后缀）
        stock_code = target.split('.')[0]
        
        st.markdown("#### 🇨🇳 A股专业数据穿透系统")
        
        # 第一排：龙虎榜 + 融资融券 + 北向资金
        col_a1, col_a2, col_a3 = st.columns(3)
        
        with col_a1:
            st.markdown("**🐯 龙虎榜追踪**")
            dragon_data = get_cn_dragon_tiger_board(stock_code)
            if dragon_data:
                st.metric("最新龙虎榜", dragon_data['latest_date'], "")
                st.metric("游资买入席位", dragon_data['buy_seats'], "")
                if dragon_data['top_buyer']:
                    st.caption(f"💡 最大买家：{dragon_data['top_buyer']}")
            else:
                st.info("暂无龙虎榜数据")
        
        with col_a2:
            st.markdown("**💰 融资融券监测**")
            margin_data = get_cn_margin_data(stock_code)
            if margin_data:
                st.metric("融资余额(亿)", f"¥{margin_data['financing_balance']:.2f}", "")
                if margin_data['financing_ratio'] > 50:
                    st.warning("⚠️ 融资占比超 50%")
            else:
                st.info("暂无融资数据")
        
        with col_a3:
            st.markdown("**🌍 北向资金动向**")
            north_data = get_cn_north_bound_data()
            if north_data:
                st.metric(f"北向净流入({north_data['date']})", f"¥{north_data['net_flow']:.2f}亿", "")
                if north_data['net_flow'] > 0:
                    st.success("✅ 外资在买入")
                else:
                    st.error("❌ 外资在卖出")
            else:
                st.info("暂无北向数据")
        
        st.markdown("---")
        
        # 第二排：两个按钮
        col_cn1, col_cn2 = st.columns(2)
        
        with col_cn1:
            btn_deepseek = st.button("🚀 启动外脑深度推演（A股专用）", use_container_width=True, key="btn_cn_deepseek")
        
        with col_cn2:
            btn_whale = st.button("🐳 巨鲸资金嗅探", type="primary", use_container_width=True, key="btn_cn_whale")
        
        if btn_deepseek:
            with st.spinner("正在从云端调取适配当前市场的量化纪律..."):
                db = load_cloud_knowledge() 
                all_rules = db["strategies"] + db["reflections"]
                filtered_rules = [r for r in all_rules if "🇨🇳" in r or "A股" in r]
                rules_text = "\n".join(filtered_rules)
                sys_inject = f"\n\n【A股专用外脑记忆库】：\n{rules_text}" if rules_text else ""
            
            p_val = price if price else "未知"
            
            improved_prompt = f"""
            你是顶级A股量化基金经理。请对 {target}（最新价 ¥{p_val}）出具深度研报。
            
            【要求】：
            1. 字数不少于 800 字
            2. 从四大维度深度拆解：基本面、情绪共振、技术面、操作指令
            3. 明确的买入/卖出信号和止损止盈位
            {sys_inject}
            """
            
            st.markdown("### 📋 A股专用深度研报")
            call_deepseek_stream(improved_prompt, system_role="作为顶级A股量化基金经理")

        if btn_whale:
            with st.spinner("正在分析巨鲸资金..."):
                hist_5d = get_historical_data(target, 
                    (datetime.datetime.now() - datetime.timedelta(days=10)).strftime('%Y-%m-%d'), 
                    datetime.datetime.now().strftime('%Y-%m-%d'))
                
                volume_data = "近期无数据"
                if not hist_5d.empty:
                    recent_data = hist_5d[['Close', 'Volume']].tail(5)
                    volume_data = recent_data.to_string()
                
                whale_prompt = f"""
                你是陆家嘴最顶级的"巨鲸资���流向嗅探犬"。标的：{target}。当前价：¥{price}。
                
                请执行【宏观机构与微观盘口双重穿透】：
                1. 该标的通常受哪些明星基金经理或国家队关注？
                2. 近期是否有新的大基金申报或清仓迹象？
                3. 龙虎榜分析与微观盘口解剖
                4. 冷血的跟庄或避险建议
                
                量价数据：{volume_data}
                """
                
                st.markdown("### 🐳 巨鲸资金嗅探")
                call_deepseek_stream(whale_prompt, system_role="你是A股盘口与机构解剖机器")

    # ==========================================
    # 4. 主界面
    # ==========================================
    st.title("机构级资产指挥台 V22 (全球三市场)")
    
    top_c1, top_c2 = st.columns([3, 1])
    with top_c1: 
        raw_target = st.text_input("🎯 锁定目标 (NVDA、0700、6758、600459 等)", "LITE", label_visibility="collapsed").upper().strip()
        
        target, market_type, market_badge, currency = identify_market(raw_target)

    with top_c2:
        price = get_current_price(target)
        if price:
            p_display = f"{currency} {price}"
            st.metric(f"📡 卫星报价 ({market_badge})", p_display)
        else:
            st.metric(f"📡 信号丢��� ({market_badge})", "未查找到该标的")

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

    tab_risk, tab_rl, tab_main, tab_brain = st.tabs([
        "🛡️ 天眼风控 (排雷)", 
        "⏳ 炼丹炉 (强化学习)", 
        "📈 量化推演 (多市场)", 
        "☁️ 云端外脑 (数据中心)"
    ])

    # 模块 A：天眼风控
    with tab_risk:
        st.markdown(f"### 🛡️ 极高权限合规审计：{target}")
        st.info("消耗算力扫描内幕交易、消息抢跑、监管问询等风险。")
        
        if st.button("🚨 启动全网舆情风控网", key="btn_risk"):
            with st.spinner("正在渗透舆情数据源..."):
                try:
                    news_data = yf.Ticker(target).news
                    headlines = [n['title'] for n in news_data][:6] if news_data else "暂无舆情"
                    
                    risk_prompt = f"""
                    你是顶级稽查员。标��：{target}。舆情线索：{headlines}。
                    请排查：
                    1. 是否存在'公告前股价提前异动'或'利好出尽暴跌'的劣迹？
                    2. 是否收到过监管问询函？
                    3. 若存在严重风险，请用【一票否决】警告。
                    """
                    st.markdown("<div class='risk-alert'>正在执行深度排雷协议，请留意红色警告...</div>", unsafe_allow_html=True)
                    call_deepseek_stream(risk_prompt, system_role="作为无情的金融监管稽查机器。")
                except:
                    st.error("舆情接口抓取受限。")

    # 模块 B：炼丹炉
    with tab_rl:
        st.markdown(f"### ⏳ 强化学习时光机：{target}")
        st.caption("截断历史数据让AI盲猜，用未来数据打脸，逼迫其生成量化纪律。")
        
        col1, col2 = st.columns(2)
        with col1: start_d = st.date_input("盲测起点", datetime.date(2023, 1, 1), key="rl_start")
        with col2: end_d = st.date_input("盲测终点", datetime.date(2023, 6, 1), key="rl_end")

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
                    
                    st.markdown(f"**📈 喂养数据**：从 {start_p} 至 {end_p}。")
                    st.markdown(f"**🔮 现实毒打**：一个月后走到 {future_p}。")
                    
                    rl_prompt = f"""
                    背景：{s_str} 到 {e_str}，{target} 从 {start_p} 至 {end_p}。
                    现实：后续一个月到了 {future_p}。
                    指令：提炼一条不超过 40 字的硬核量化纪律。
                    """
                    
                    st.markdown("### 🔴 历史左右互搏流")
                    call_deepseek_stream(rl_prompt)
                    
                    if st.session_state.ds_key:
                        try:
                            res = call_deepseek_non_stream(rl_prompt + "请只输出那条 40 字以内的纪律本身。")
                            if res:
                                market_tag = {
                                    "US_STOCK": "🇺🇸",
                                    "HK_STOCK": "🇭🇰",
                                    "JP_STOCK": "🇯🇵",
                                    "A_SHARE_SH": "🇨🇳",
                                    "A_SHARE_SZ": "🇨🇳",
                                }.get(market_type, "🌍")
                                insert_cloud_memory("reflection", f"【时光机 - {target}】{market_tag}: {res}")
                                st.success(f"✅ 纪律已写入云端：{res}")
                        except: pass

    # 模块 C：主干量化推演 - 多市场版
    with tab_main:
        st.markdown(f"### 📈 实时穿透：{target} ({market_badge})")
        
        if market_type == "US_STOCK":
            st.markdown("""
            <div class="us-card">
            <h4>🇺🇸 华尔街机构级分析</h4>
            </div>
            """, unsafe_allow_html=True)
            display_us_stock_analysis(target, price)
            
            if st.button("💡 启动 AI 华尔街策略顾问", use_container_width=True, key="btn_us_ai"):
                with st.spinner("正在连接华尔街数据库..."):
                    db = load_cloud_knowledge()
                    us_rules = [r for r in (db["strategies"] + db["reflections"]) if "🇺🇸" in r or "美股" in r]
                    us_inject = "\n".join(us_rules) if us_rules else "(美股外脑为空)"
                    
                    us_prompt = f"""
                    你是华尔街 25 年的老牌对冲基金经理。
                    {target}（当前价 ${price}）现在该不该买？三个月目标价？
                    
                    请给出 800+ 字的冷酷、精确的交易建议。
                    
                    维度：技术面、期权市场、基本面、宏观风险、机构动向、操作指令
                    
                    参考纪律：{us_inject}
                    """
                    
                    st.markdown("### 🎯 华尔街老兵的冷血建议")
                    call_deepseek_stream(us_prompt, system_role="你是华尔街 25 年的资深操盘手，分析必须精确、冷酷。")
        
        elif market_type == "HK_STOCK":
            st.markdown("""
            <div class="hk-card">
            <h4>🇭🇰 港股深度分析系统</h4>
            </div>
            """, unsafe_allow_html=True)
            display_hk_stock_analysis(target, price)
            
            if st.button("💡 启动 AI 港股策略顾问", use_container_width=True, key="btn_hk_ai"):
                with st.spinner("正在分析港股..."):
                    hk_prompt = f"""
                    你是香港投资银行的首席分析师。
                    {target}（当前价 HK${price}）现在该不该买？
                    
                    请给出 800+ 字的分析，包括：
                    1. 香港市场的流动性情况（北向资金、港资情绪）
                    2. 该股相对 H 股指数的位置
                    3. 与 A 股同步股的对标（如果有）
                    4. 明确的操作建议
                    """
                    
                    st.markdown("### 🎯 香港投行的专业建议")
                    call_deepseek_stream(hk_prompt, system_role="你是香港投资银行的首席分析师，对港股市场了如指掌。")
        
        elif market_type == "JP_STOCK":
            st.markdown("""
            <div class="jp-card">
            <h4>🇯🇵 日股深度分析系统</h4>
            </div>
            """, unsafe_allow_html=True)
            display_jp_stock_analysis(target, price)
            
            if st.button("💡 启动 AI 日股策略顾问", use_container_width=True, key="btn_jp_ai"):
                with st.spinner("正在分析日股..."):
                    jp_prompt = f"""
                    你是东京大型券商的首席分析师。
                    {target}（当前价 ¥{price}）现在该不该买？
                    
                    请给出 800+ 字的分析，包括：
                    1. 日本市场的宏观环境（日银政策、日经走势）
                    2. 该股的基本面与增长前景
                    3. 汇率对该股的影响
                    4. 明确的操作建议
                    """
                    
                    st.markdown("### 🎯 东京券商的专业建议")
                    call_deepseek_stream(jp_prompt, system_role="你是东京大型券商的首席分析师，对日股市场深有研究。")
        
        else:
            st.markdown("""
            <div class="cn-card">
            <h4>🇨🇳 A股专业机构分析系统</h4>
            </div>
            """, unsafe_allow_html=True)
            display_cn_stock_analysis(target, price)

    # 模块 D：云端外脑
    with tab_brain:
        st.markdown("### ☁️ 云端 RAG 向量记忆中心")
        st.caption("支持手动喂养，或直接上传 PDF/Word/PPT 研报。")
        
        c_feed1, c_feed2 = st.columns([1, 1])
        
   with c_feed1:
            st.markdown("**📝 1. 碎片战法投喂**")
            feed_text = st.text_area("粘贴聊天记录或大白话", placeholder="例如：MACD 金叉 + RSI < 30 是美股黄金买点...", key="feed_text")
            
            if st.button("🧠 提炼文本并刻入云端", key="btn_text_feed"):
                if feed_text and st.session_state.ds_key:
                    with st.spinner("正在提炼规则..."):
                        # 安全调用 DeepSeek（非流式），并把用户文本传进去
                        prompt = (
                            "将以下内容转化为一条极其精简、冷酷的量化纪律(不超过50字)，"
                            "并在末尾标注市场标签：A股(🇨🇳) / 美股(🇺🇸) / 港股(🇭🇰) / 日股(🇯🇵)。\n\n"
                            f"原文：{feed_text}"
                        )
                        res = call_deepseek_non_stream(prompt, max_tokens=300)
                        
                        if res:
                            insert_cloud_memory("strategy", f"【手动植入】: {res}")
                            st.success("✅ 战法已写入云端！")
                            time.sleep(1)
                            st.rerun()
                elif not st.session_state.ds_key:
                    st.error("缺少 API Key。")

        with c_feed2:
            st.markdown("**📂 2. 文档自动榨取**")
            uploaded_file = st.file_uploader("支持 PDF/Word/PPT/TXT", type=['pdf', 'docx', 'pptx', 'txt'])
            
            if st.button("🧬 启动文档深度榨取", key="btn_doc_feed"):
                if uploaded_file is not None and st.session_state.ds_key:
                    with st.spinner("正在破译文档..."):
                        extracted_text = ""
                        try:
                            if uploaded_file.name.endswith('.pdf'):
                                import PyPDF2
                                pdf_reader = PyPDF2.PdfReader(uploaded_file)
                                for page in pdf_reader.pages:
                                    text = page.extract_text()
                                    if text: 
                                        extracted_text += text + "\n"
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
                                st.warning("文档为空或全是图片。")
                            else:
                                st.info(f"成功提取 {len(extracted_text)} 字，正在榨取...")
                                safe_text = extracted_text[:20000]
                                
                                prompt = f"""
                                从以下文档中榨取 3-6 条最硬核的量化纪律。
                                要求：每条 50 字以内，标注市场(美股/港股/日股/A股)。
                                
                                文档：{safe_text}
                                """
                                res = call_deepseek_non_stream(prompt, max_tokens=2000)
                                
                                if res:
                                    new_rules = [r.strip() for r in res.split('\n') if r.strip() and len(r) > 5]
                                    for rule in new_rules:
                                        insert_cloud_memory("strategy", f"【研报】: {rule}")
                                    
                                    st.success(f"✅ 成功榨取 {len(new_rules)} 条战法！")
                                    time.sleep(1.5)
                                    st.rerun()
                        except Exception as e:
                            st.error(f"文档解析失败: {e}")
        
        st.markdown("---")
        all_records = get_all_cloud_memories()
        
        if all_records:
            options_dict = {record['id']: record['content'] for record in all_records}
            selected_ids = st.multiselect("圈选要删除的纪律：", options=list(options_dict.keys()), format_func=lambda x: options_dict[x])
            
            if st.button("�� 彻底抹除", type="primary"):
                if selected_ids:
                    delete_cloud_memories(selected_ids)
                    st.success("✅ 删除成功！")
                    time.sleep(1)
                    st.rerun()
            
            st.markdown("---")
            st.markdown("**📚 当前系统脑容量**")
            for record in all_records:
                st.markdown(f"<div class='knowledge-card'>{record['content']}</div>", unsafe_allow_html=True)
        else:
            st.info("外脑为空，快去喂养数据吧！")
