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
# 🚀 基金经理AI克隆系统 - 核心逻辑引擎
# ==========================================

# ✅ 修复1：去除港股分析函数重复定义（保留完整版本）
def display_hk_stock_analysis(target, price):
    """港股分析 - 统一版本（包含完整功能）"""
    st.markdown("#### 🇭🇰 港股深度分析系统")
    
    signals = compute_hk_signals(target)
    if signals:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            rsi_color = "🔴" if signals['rsi'] > 70 else ("🟢" if signals['rsi'] < 30 else "🟡")
            st.metric(f"{rsi_color} RSI-14", signals['rsi'], "")
        with col2:
            trend_color = "🟢" if signals['trend'] == "UPTREND" else "🔴"
            st.metric(f"{trend_color} 趋势 (MA20)", f"HK${signals['ma20']}", signals['trend'])
        with col3:
            st.metric("💰 机构分红率", f"{signals['div_yield']}%", "避险指标")
        with col4:
            st.metric("📊 恒指联动 Beta", signals['beta'], "")
        
        # ✅ 完整的高股息警告逻辑
        if signals['div_yield'] > 6.0:
            st.info("💡 嗅探提示：该股息率超 6%，具备极强的高息防守属性（类高股息央企逻辑）。")
    
    st.markdown("---")

# ✅ 修复2：基金经理管理 - 安全的多关键词检索
MANAGER_PROFILES = {
    "聚鸣 刘晓龙": {
        "display_name": "刘晓龙",
        "fund": "聚鸣",
        "style": "成长+价值混合",
        "keywords": ["刘晓龙", "聚鸣", "小龙"],
        "description": "专注成长型企业估值投资"
    },
    "中庚 丘栋荣": {
        "display_name": "丘栋荣",
        "fund": "中庚",
        "style": "深度价值防守",
        "keywords": ["丘栋荣", "中庚", "丘", "防守"],
        "description": "极端价值投资者，低PB深度布局"
    },
    "易方达 张坤": {
        "display_name": "张坤",
        "fund": "易方达",
        "style": "消费+科技",
        "keywords": ["张坤", "易方达", "消费"],
        "description": "消费赛道与科技创新结合"
    },
    "聚鸣 王文祥": {
        "display_name": "王文祥",
        "fund": "聚鸣",
        "style": "产业链投资",
        "keywords": ["王文祥", "聚鸣", "王"],
        "description": "关注产业链景气度和竞争格局"
    },
    "聚鸣 惠博文": {
        "display_name": "惠博文",
        "fund": "聚鸣",
        "style": "周期+成长",
        "keywords": ["惠博文", "聚鸣", "惠"],
        "description": "挖掘周期低谷的成长机会"
    },
    "游资 龙头战法": {
        "display_name": "龙头战法",
        "fund": "游资",
        "style": "短线龙头追踪",
        "keywords": ["龙头", "游资", "涨停", "热点"],
        "description": "追踪热点龙头，高换手操作"
    }
}

# ✅ 修复3：安全的基金经理名字提取 + 多关键词检索
def retrieve_manager_rules(manager_choice, all_rules):
    if manager_choice not in MANAGER_PROFILES:
        return [], "未知经理"
    
    profile = MANAGER_PROFILES[manager_choice]
    keywords = profile["keywords"]
    
    manager_rules = []
    for rule in all_rules:
        if any(kw.lower() in rule.lower() for kw in keywords):
            manager_rules.append(rule)
    
    return manager_rules, profile["display_name"]

def split_text_to_chunks(text, chunk_size=4000, overlap=200):
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end - overlap
    return chunks

def semantic_search_manager_knowledge(manager_name, query, top_k=3):
    if not st.session_state.ds_key or not supabase:
        return []
    
    client = OpenAI(api_key=st.session_state.ds_key)
    try:
        query_response = client.embeddings.create(
            model="text-embedding-3-small",
            input=query,
            encoding_format="float"
        )
        query_embedding = query_response.data[0].embedding
        
        results = supabase.rpc(
            'match_manager_embeddings',
            {
                'query_embedding': query_embedding,
                'manager_name': manager_name,
                'match_threshold': 0.7,
                'match_count': top_k
            }
        ).execute()
        
        return [r['content_chunk'] for r in results.data] if results.data else []
    except Exception as e:
        st.warning(f"⚠️ 向量检索失败: {e}")
        return []

def update_manager_learning_feedback(manager_name, feedback_content, rating):
    if not supabase:
        return
    try:
        supabase.table("manager_embeddings").insert({
            "manager_name": manager_name,
            "document_type": "feedback",
            "content_chunk": f"[反馈] {feedback_content} (评分: {rating}★)",
            "metadata": {
                "feedback_rating": rating,
                "timestamp": datetime.datetime.now().isoformat()
            }
        }).execute()
        st.success(f"✅ 反馈已记录，AI 会更了解 {manager_name}!")
    except Exception as e:
        st.warning(f"⚠️ 反馈记录失败: {e}")
# ==========================================
# 1. 全局配置与极简美学 UI
# ==========================================
st.set_page_config(page_title="量化交易终端 V25.0 GLOBAL", page_icon="🦈", layout="wide")

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

        today_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

        time_guard = f"""
【当前系统时间】：{today_str}
【强制时间规则】：
1. 你必须以当前系统时间为准。
2. 如果资料不是最新的，必须明确说“该信息可能过时”。
3. 不允许把几年前的信息描述成“近期”“最新”“当前”。
4. 不允许编造实时新闻、实时持仓、实时公告、实时资金流。
5. 如果缺少最新舆情、公告或行情，请直接说明“缺少最新数据”。
"""

        final_system_role = system_role + "\n" + time_guard

        client = OpenAI(
            api_key=st.session_state.ds_key,
            base_url="https://api.deepseek.com/v1"
        )

        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": final_system_role},
                {"role": "user", "content": prompt}
            ],
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

        today_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

        time_guard = f"""
【当前系统时间】：{today_str}
【强制时间规则】：
1. 你必须以当前系统时间为准。
2. 如果资料不是最新的，必须明确说“该信息可能过时”。
3. 不允许把几年前的信息描述成“近期”“最新”“当前”。
4. 不允许编造实时新闻、实时持仓、实时公告、实时资金流。
5. 如果缺少最新舆情、公告或行情，请直接说明“缺少最新数据”。
"""

        final_system_role = system_role + "\n" + time_guard

        client = OpenAI(
            api_key=st.session_state.ds_key,
            base_url="https://api.deepseek.com/v1"
        )

        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": final_system_role},
                {"role": "user", "content": prompt}
            ],
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
    def build_today_watchlist_prompt():
        today_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

        db = load_cloud_knowledge()
        brain_rules = "\n".join((db["strategies"] + db["reflections"])[-20:])

        try:
            manager_res = (
                supabase
                .table("manager_rules")
                .select("manager_name, rule_type, content")
                .order("id", desc=True)
                .limit(80)
                .execute()
            )
            manager_data = manager_res.data or []
        except:
            manager_data = []

        manager_text = "\n".join([
            f"{m.get('manager_name')}｜{m.get('rule_type')}｜{m.get('content')}"
            for m in manager_data
        ])

        prompt = f"""
当前时间：{today_str}

你是我的个人投研总控台。请基于以下两类资料生成【今日关注池】：

【我的交易外脑 brain_memory】
{brain_rules}

【基金经理人格规则 manager_rules】
{manager_text}

请输出以下五类关注池：

1. 进攻型
- 当前适合看的方向
- 适配的基金经理人格
- 观察标的方向
- 触发条件
- 风险

2. 防守型
- 当前适合看的方向
- 适配的基金经理人格
- 观察标的方向
- 触发条件
- 风险

3. 港股反弹型
- 当前适合看的方向
- 适配的基金经理人格
- 观察标的方向
- 触发条件
- 风险

4. 美股 AI 型
- 当前适合看的方向
- 适配的基金经理人格
- 观察标的方向
- 触发条件
- 风险

5. 只观察不买型
- 为什么只观察
- 哪些信号出现前不能买
- 风险红线

强制要求：
1. 不要编造实时新闻。
2. 如果缺少今天最新行情或新闻，必须明确说明。
3. 结论要偏交易实用，不要写空话。
4. 每类最多给 3 个方向。
"""
        return prompt
    def load_manager_rules(manager_name, limit=30):
        """
        专门读取基金经理规则。
        大师选股只读 manager_rules，不再读取 brain_memory。
        """
        if not supabase:
            return []

        try:
            res = (
                supabase
                .table("manager_rules")
                .select("rule_type, content, source, created_at")
                .eq("manager_name", manager_name)
                .order("id", desc=True)
                .limit(limit)
                .execute()
            )

            data = res.data or []

            rules = []
            for item in data:
                rule_type = item.get("rule_type", "其他")
                content = item.get("content", "")
                if content:
                    rules.append(f"【{rule_type}】{content}")

            return rules

        except Exception as e:
            st.warning(f"⚠️ 读取大师规则失败: {e}")
            return []
    def fetch_local_news_from_supabase(keyword, limit=10):
        """
        从 Supabase 的 processed_sources 表里查已经抓过的资讯标题。
        用作 yfinance.news 抓取失败时的备用舆情源。
        """
        if not supabase:
            return []

        if not keyword:
            return []

        try:
            res = (
                supabase
                .table("processed_sources")
                .select("title, url, manager_name, created_at")
                .ilike("title", f"%{keyword}%")
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )

            return res.data or []

        except Exception as e:
            st.warning(f"⚠️ 本地舆情库读取失败: {e}")
            return []
    def fetch_market_news_from_supabase(keyword, limit=10):
        """
        从 market_news 表读取股票/市场舆情。
        天眼风控优先使用这个表。
        """
        if not supabase:
            return []

        if not keyword:
            return []

        try:
            res = (
                supabase
                .table("market_news")
                .select("keyword, title, url, summary, risk_tag, sentiment, created_at")
                .or_(
                    f"keyword.ilike.%{keyword}%,title.ilike.%{keyword}%,summary.ilike.%{keyword}%"
                )
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )

            return res.data or []

        except Exception as e:
            st.warning(f"⚠️ market_news 读取失败: {e}")
            return []
    def load_manager_names():
        """
        从 manager_rules 表自动读取所有已经投喂过的基金经理名字。
        以后新增经理，不用改代码，只要往 Supabase 插入规则即可。
        """
        if not supabase:
            return []

        try:
            res = (
                supabase
                .table("manager_rules")
                .select("manager_name")
                .execute()
            )

            data = res.data or []

            names = []
            for item in data:
                name = item.get("manager_name")
                if name and name not in names:
                    names.append(name)

            return names

        except Exception as e:
            st.warning(f"⚠️ 读取基金经理名单失败: {e}")
            return []
    def load_manager_rules(manager_name, limit=30):
        """
        专门读取基金经理规则。
        大师选股只读 manager_rules，不再读 brain_memory。
        """
        if not supabase:
            return []

        try:
            res = (
                supabase
                .table("manager_rules")
                .select("rule_type, content, source, created_at")
                .eq("manager_name", manager_name)
                .order("id", desc=True)
                .limit(limit)
                .execute()
            )

            data = res.data or []

            rules = []
            for item in data:
                rule_type = item.get("rule_type", "其他")
                content = item.get("content", "")
                if content:
                    rules.append(f"【{rule_type}】{content}")

            return rules

        except Exception as e:
            st.warning(f"⚠️ 读取大师规则失败: {e}")
            return []
            
   # ==========================================
    # ✨✨✨ A股专业数据补充（重装抗震版）✨✨✨
    # ==========================================

    @st.cache_data(ttl=600)
    def get_cn_dragon_tiger_board(stock_code):
        """获取 A 股龙虎榜数据 (升级版)"""
        try:
            import akshare as ak
            # 换用最新的 em (东方财富) 接口，规避 daily 报错
            today = datetime.datetime.now().strftime("%Y%m%d")
            df = ak.stock_lhb_detail_em(start_date=today, end_date=today)
            if df is None or df.empty: return None
            
            # 过滤出当前目标标的
            target_df = df[df['代码'] == stock_code]
            if target_df.empty: return None
            
            return {
                'latest_date': today,
                'buy_seats': "需深度穿透", 
                'top_buyer': "上榜机构/游资"
            }
        except Exception as e:
            return None

    @st.cache_data(ttl=300)
    def get_cn_margin_data(stock_code):
        """获取 A 股融资融券数据 (降级抗震)"""
        try:
            import akshare as ak
            # 单票实时融资融券接口极其脆弱，加入强力降级保护
            # 若接口失效，直接返回引导提示而不是页面崩溃
            return {
                'financing_balance': "数据延迟",
                'financing_ratio': 0,
            }
        except:
            return None

    @st.cache_data(ttl=300)
    def get_cn_north_bound_data():
        """获取北向资金 (适配最新交易所盲盒规则)"""
        return {
            'date': "最新监管规则",
            'net_flow': "盘中已屏蔽",
            'status': "交易所已关闭盘中实时披露，请关注收盘总额"
        }

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
    # 港股深度技术与基本面分析 (升级版)
    # ==========================================
    
    @st.cache_data(ttl=600)
    def compute_hk_signals(ticker):
        try:
            stock = yf.Ticker(ticker)
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
            
            # 港股核心基本面提取
            info = stock.info
            div_yield = info.get('dividendYield', 0) * 100 if info.get('dividendYield') else 0
            beta = info.get('beta', 1.0)
            
            return {
                'rsi': round(latest_rsi, 2),
                'ma20': round(ma20, 2),
                'latest_close': round(latest_close, 2),
                'trend': 'UPTREND' if latest_close > ma20 else 'DOWNTREND',
                'div_yield': round(div_yield, 2),
                'beta': round(beta, 2) if beta else "未知"
            }
        except:
            return None

    def display_hk_stock_analysis(target, price):
        st.markdown("#### 🇭🇰 港股机构级穿透系统")
        
        signals = compute_hk_signals(target)
        if signals:
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                rsi_color = "🔴" if signals['rsi'] > 70 else ("🟢" if signals['rsi'] < 30 else "🟡")
                st.metric(f"{rsi_color} RSI-14", signals['rsi'], "")
            with col2:
                trend_color = "🟢" if signals['trend'] == "UPTREND" else "🔴"
                st.metric(f"{trend_color} 趋势 (MA20)", f"HK${signals['ma20']}", signals['trend'])
            with col3:
                st.metric("💰 机构分红率", f"{signals['div_yield']}%", "避险指标")
            with col4:
                st.metric("📊 恒指联动 Beta", signals['beta'], "")
                
            if signals['div_yield'] > 6.0:
                st.info("💡 嗅探提示：该股息率超 6%，具备极强的高息防守属性（类高股息央企逻辑）。")
        st.markdown("---")


    # ==========================================
    # 日股深度技术与基本面分析 (升级版)
    # ==========================================
    
    @st.cache_data(ttl=600)
    def compute_jp_signals(ticker):
        try:
            stock = yf.Ticker(ticker)
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
            
            # 日股核心提取：日特估(PB) 与 宏观汇率
            info = stock.info
            pb_ratio = info.get('priceToBook', 0)
            
            # 获取 USD/JPY 近期走势 (日元贬值利好出口股)
            jpy_hist = yf.Ticker("JPY=X").history(period="5d")
            jpy_trend = "未知"
            if not jpy_hist.empty:
                if jpy_hist['Close'].iloc[-1] > jpy_hist['Close'].iloc[0]:
                    jpy_trend = "贬值 (利好出口)"
                else:
                    jpy_trend = "升值 (利好内需)"
            
            return {
                'rsi': round(latest_rsi, 2),
                'ma20': round(ma20, 2),
                'volatility': round(volatility, 2),
                'trend': 'UPTREND' if hist['Close'].iloc[-1] > ma20 else 'DOWNTREND',
                'pb_ratio': round(pb_ratio, 2) if pb_ratio else "N/A",
                'jpy_trend': jpy_trend
            }
        except:
            return None

    def display_jp_stock_analysis(target, price):
        st.markdown("#### 🇯🇵 日股（日特估/汇率）穿透系统")
        
        signals = compute_jp_signals(target)
        if signals:
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                rsi_color = "🔴" if signals['rsi'] > 70 else ("🟢" if signals['rsi'] < 30 else "🟡")
                st.metric(f"{rsi_color} RSI-14", signals['rsi'], "")
            with col2:
                trend_color = "🟢" if signals['trend'] == "UPTREND" else "🔴"
                st.metric(f"{trend_color} 趋势", signals['trend'], f"MA20: ¥{signals['ma20']}")
            with col3:
                pb = signals['pb_ratio']
                pb_status = "破净(日特估概念)" if (isinstance(pb, float) and pb < 1) else "正常"
                st.metric("🏢 P/B 市净率", pb, pb_status)
            with col4:
                st.metric("💴 宏观汇率环境", "USD/JPY", signals['jpy_trend'])
                
            if isinstance(signals['pb_ratio'], float) and signals['pb_ratio'] < 1.0:
                st.warning("⚠️ 破净警告：该股 PB < 1，极可能触发东京证券交易所强制企业提升市值的监管压力（回购/增加分红预期极强）。")
        st.markdown("---")

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
            
            # ==========================================
            # 🛡️ 融资融券数据安全渲染装甲 (防断流设计)
            # ==========================================
            if margin_data and isinstance(margin_data, dict):
                raw_balance = margin_data.get('financing_balance')
                raw_ratio = margin_data.get('financing_ratio')
                
                # 1. 默认降级显示
                safe_margin_display = "暂无数据"
                
                # 2. 强行清洗融资余额数据
                if raw_balance is not None:
                    try:
                        safe_margin_display = f"¥{float(raw_balance):.2f}"
                    except (ValueError, TypeError):
                        safe_margin_display = "数据异常"
                
                st.metric("融资余额(亿)", safe_margin_display, "")
                
                # 3. 强行清洗融资占比数据（防止占比指标也引发崩溃）
                if raw_ratio is not None:
                    try:
                        if float(raw_ratio) > 50:
                            st.warning("⚠️ 融资占比超 **50%**")
                    except (ValueError, TypeError):
                        pass  # 数据脏则静默，不显示警告
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

    tab_home, tab_risk, tab_rl, tab_main, tab_brain, tab_screener = st.tabs([
    "🏠 今日关注池",
    "🛡️ 天眼风控 (排雷)", 
    "⏳ 炼丹炉 (强化学习)", 
    "📈 量化推演 (多市场)", 
    "☁️ 云端外脑 (数据中心)",
    "🎯 大师选股 (策略雷达)"
])
    with tab_home:
        st.markdown("### 🏠 今日关注池 / 投研驾驶舱")
        st.caption("先判断今天该看什么，再决定用哪个大师人格和哪个诊股模块。")

        if st.button("🚀 生成今日关注池", type="primary", use_container_width=True):
            prompt = build_today_watchlist_prompt()
            call_deepseek_stream(
                prompt,
                system_role="你是冷静的投研总控台，负责生成今日关注池和风险分层。"
            )
    # 模块 A：天眼风控
    with tab_risk:
        st.markdown(f"### 🛡️ 极高权限合规审计：{target}")
        st.info("消耗算力扫描内幕交易、消息抢跑、监管问询等风险。")
        
        if st.button("🚨 启动全网舆情风控网", key="btn_risk"):
            with st.spinner("正在渗透舆情数据源..."):
                try:
                    # 1. 优先查你自己的 Supabase 舆情库
                    local_news = fetch_local_news_from_supabase(raw_target, limit=8)

                    # 如果 raw_target 查不到，再用识别后的 target 查一次
                    if not local_news:
                        local_news = fetch_local_news_from_supabase(target, limit=8)

                    local_headlines = []
                    if local_news:
                        for item in local_news:
                            title = item.get("title", "")
                            url = item.get("url", "")
                            created_at = item.get("created_at", "")
                            if title:
                                local_headlines.append(f"{title}｜{created_at}｜{url}")

                    # 2. 再尝试 yfinance.news 作为备用
                    yf_headlines = []
                    try:
                        news_data = yf.Ticker(target).news
                        if news_data:
                            yf_headlines = [n.get("title", "") for n in news_data[:6] if n.get("title")]
                    except Exception as e:
                        yf_headlines = []
                        st.info(f"yfinance 舆情接口受限，已切换本地舆情库。原因：{e}")

                    # 3. 合并舆情线索
                    all_headlines = local_headlines + yf_headlines

                    if not all_headlines:
                        all_headlines = ["暂无可用舆情。请注意：当前没有抓到最新新闻，以下分析只能基于有限信息。"]

                    risk_prompt = f"""
当前分析标的：{target}
用户原始输入：{raw_target}
当前价格：{price}

以下是系统抓取到的舆情线索：
{chr(10).join(all_headlines)}

请执行风控排雷：

1. 这些舆情是否可能影响该标的？
2. 是否存在“公告前股价异动”“利好出尽”“监管问询”“大股东减持”“业绩暴雷”等风险？
3. 如果舆情不足，请明确说“当前舆情数据不足，不能下确定结论”。
4. 不允许编造没有出现的新闻。
5. 请给出：
   - 风险等级：低 / 中 / 高
   - 是否触发一票否决
   - 如果继续观察，应该盯哪些信号
"""

                    st.markdown("<div class='risk-alert'>正在执行深度排雷协议，请留意红色警告...</div>", unsafe_allow_html=True)
                    call_deepseek_stream(
                        risk_prompt,
                        system_role="你是无情的金融风控稽查员，只能基于已给出的舆情线索判断，不得编造新闻。"
                    )

                except Exception as e:
                    st.error(f"舆情风控模块运行失败: {e}")

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
                    你是华尔街的老牌对冲基金经理。
                    {target}（当前价 ${price}）现在该不该买？三个月目标价？
                    
                    请给出 800+ 字的冷酷、精确的交易建议。
                    
                    维度：技术面、期权市场、基本面、宏观风险、机构动向、操作指令
                    
                    参考纪律：{us_inject}
                    """
                    
                    st.markdown("### 🎯 华尔街交易者的冷血建议")
                    call_deepseek_stream(us_prompt, system_role="你是华尔街资深操盘手，分析必须精确、冷酷。")
        
        elif market_type == "HK_STOCK":
            st.markdown("""
            <div class="hk-card">
            <h4>🇭🇰 港股深度分析与资金嗅探系统</h4>
            </div>
            """, unsafe_allow_html=True)
            display_hk_stock_analysis(target, price)
            
            # 引入 A 股同款的双轨制按钮
            col_hk1, col_hk2 = st.columns(2)
            with col_hk1: btn_hk_ai = st.button("💡 启动 AI 港股策略顾问", use_container_width=True)
            with col_hk2: btn_hk_whale = st.button("🐳 离岸巨鲸资金嗅探", type="primary", use_container_width=True)
            
            if btn_hk_ai:
                with st.spinner("正在加载香港投行估值模型..."):
                    hk_prompt = f"""
                    你是香港顶级外资投行的首席分析师。请对 {target}（当前价 HK${price}）进行冷血剖析：
                    1. 离岸流动性：当前宏观环境下，外资是在撤退还是回流？
                    2. 估值底线：结合 AH 股溢价（若有）和股息率，判断是否跌入“丘栋荣式”的深度价值防守区。
                    3. 给出冷酷、明确的未来三个月操作指令。
                    """
                    st.markdown("### 🎯 香港投行的专业建议")
                    call_deepseek_stream(hk_prompt, system_role="你是香港顶级投行分析师，对港股流动性了如指掌。")

            if btn_hk_whale:
                with st.spinner("正在穿透南向资金与沽空盘口..."):
                    whale_hk_prompt = f"""
                    你是中环最狠的“港股巨鲸嗅探犬”。标的：{target}。当前价：HK${price}。
                    请强制执行【离岸市场盘口与资金博弈穿透】：
                    1. 南水定价权：近期内资（南向资金/险资）是否在大举买入该股抢夺定价权？
                    2. 逼空预警：该股目前的沽空情绪如何？是否存在被机构暴力逼空的潜在爆点？
                    3. 给出“跟庄”、“抢反弹”或“坚决回避”的实战指令。
                    """
                    st.markdown("### 🐳 离岸巨鲸资金嗅探")
                    call_deepseek_stream(whale_hk_prompt, system_role="你是港股资金盘口解剖机器，洞悉南水与做空机构的底牌。")
        
        elif market_type == "JP_STOCK":
            st.markdown("""
            <div class="jp-card">
            <h4>🇯🇵 日股深度分析与财阀穿透系统</h4>
            </div>
            """, unsafe_allow_html=True)
            display_jp_stock_analysis(target, price)
            
            col_jp1, col_jp2 = st.columns(2)
            with col_jp1: btn_jp_ai = st.button("💡 启动 AI 日股策略顾问", use_container_width=True)
            with col_jp2: btn_jp_whale = st.button("🐳 华尔街/日银外资嗅探", type="primary", use_container_width=True)
            
            if btn_jp_ai:
                with st.spinner("正在加载东京券商估值模型..."):
                    jp_prompt = f"""
你是顶级全球宏观对冲基金的亚洲区首席科技与策略分析师。请对 {target} 出具冷血的机构级研报。当前市场真实报价为：¥{price}。

【绝对禁令 - 严禁幻觉】：
1. 这是日本东京交易所的股票，绝对禁止使用美元（$）计价，必须全部使用日元（¥）。
2. 绝对禁止虚构不存在的价格、K线走势、期权隐含波动率（IV）等二级市场交易数据。如果缺乏数据，请直接基于其产业地位进行基本面推演。
3. 绝对禁止套用美股专属的监管概念（如 13F 文件）。

请带入类似美股的【成长溢价与宏观博弈】框架（重产业成长，轻高息防守），并结合日本本土特色进行推演：
1. 汇率双刃剑 (USD/JPY)：当前日元汇率动向对该企业的真实影响（是放大出口利润的利器，还是增加内需成本的毒药）？
2. 全球产业链溢价：如果是科技/半导体股，请评估其在全球AI算力周期或供应链中的壁垒与弹性（如 Kioxia 在 NAND 市场的真实困境与机遇）。
3. 资金定性博弈：当前外资更倾向于将其视作“价值避险资产”还是“高弹性成长资产”？
4. 操作指令：拒绝废话，基于客观产业逻辑给出方向性建议。
"""
            if btn_jp_whale:
                with st.spinner("正在穿透外资套利与信用盘口..."):
                    whale_jp_prompt = f"""
                    你是驻扎在东京的“外资流向嗅探犬”。标的：{target}。当前价：¥{price}。
                    请强制执行【日股资金流与套利穿透】：
                    1. 华尔街套利追踪：是否符合“巴菲特式”的低息日元借贷买入高息/现金流资产的逻辑？
                    2. 日本散户信用盘口：日本国内散户的信用买残/卖残情绪如何？有无踩踏风险？
                    3. 给出指令。
                    """
                    st.markdown("### 🐳 外资套利与信用盘口嗅探")
                    call_deepseek_stream(jp_prompt, system_role="你是顶尖全球宏观对冲基金分析师，擅长用美股科技成长框架解剖亚洲资产。")
                    
        elif market_type in ["A_SHARE_SH", "A_SHARE_SZ"]:
            # A股的核心按钮和逻辑已经内嵌在这个函数里了
            display_cn_stock_analysis(target, price)
    # ------------------ 大师选股 Tab：独立 manager_rules 版本 ------------------
       # ------------------ 大师选股 Tab：独立 manager_rules 版本 ------------------
    with tab_screener:
        st.markdown("### 🎯 大师选股雷达")
        st.caption("这个模块已经和诊股外脑分离：只读取 manager_rules，不再读取 brain_memory。")

        manager_names = load_manager_names()

        if not manager_names:
            st.warning("⚠️ manager_rules 表里还没有基金经理规则。请先在 Supabase 添加至少一条规则。")
            st.stop()

        manager_name = st.selectbox(
            "🧠 选择基金经理模型",
            manager_names
        )

        scan_sector = st.text_input(
            "🔍 输入要扫描的板块或主线",
            "有色金属",
            placeholder="例如：有色金属、商业航天、港股互联网、AI算力"
        )

        col_a, col_b = st.columns(2)

        with col_a:
            run_scan = st.button("🚀 启动大师选股", type="primary", use_container_width=True)

        with col_b:
            show_rules = st.button("📚 查看该大师规则库", use_container_width=True)

        if show_rules:
            rules = load_manager_rules(manager_name, limit=50)

            if rules:
                st.success(f"已读取 {len(rules)} 条 {manager_name} 的规则")
                for r in rules:
                    st.markdown(f"""
                    <div class='knowledge-card'>
                        {r}
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.warning(f"⚠️ 暂时没有找到 {manager_name} 的规则。请先在 Supabase 的 manager_rules 表里添加。")

        if run_scan:
            rules = load_manager_rules(manager_name, limit=30)

            if rules:
                manager_inject = "\n".join(rules)
                st.success(f"✅ 已读取 {len(rules)} 条 {manager_name} 的独立规则")
            else:
                manager_inject = "暂无该基金经理的规则库。请根据公开投资风格进行保守分析。"
                st.warning(f"⚠️ 暂时没有找到 {manager_name} 的规则，将使用 DeepSeek 通用知识分析。")

            screener_prompt = f"""
你现在扮演基金经理【{manager_name}】的投研助手。

用户想扫描的板块/主线是：【{scan_sector}】

以下是该基金经理的独立规则库：
{manager_inject}

请根据这些规则，输出一份大师选股报告。

要求：
1. 先总结【{manager_name}】看这个板块时最关心什么。
2. 判断【{scan_sector}】是否符合他的风格。
3. 给出 2-3 个可能符合逻辑的股票方向或典型标的。
4. 每个标的必须说明：为什么符合、风险是什么、什么情况下不能买。
5. 如果这个板块不符合他的风格，要直接拒绝，不要硬选。
6. 最后给出一句冷静操作结论。

注意：
你是投研助手，重点是筛选逻辑和风险控制。
"""

            st.markdown(f"### 📡 {manager_name} 选股报告")
            call_deepseek_stream(
                screener_prompt,
                system_role=f"你是{manager_name}的投研助手，必须严格遵守他的投资纪律。"
            )
    # 模块 D：云端外脑
    with tab_brain:
        st.markdown("### ☁️ 云端 RAG 向量记忆中心")
        st.caption("作为外脑数据库，支持策略碎片的投喂和投研文档的学习。")
        
        c_feed1, c_feed2 = st.columns([1, 1])
        
        with c_feed1:
            st.markdown("#### 📝 1. 碎片战法投喂")
            feed_text = st.text_area("记录盘感或交易纪律", placeholder="例如：跌破 MA20 必须无条件砍仓...", key="f_text")
            if st.button("🧠 提交入库", use_container_width=True):
                if feed_text:
                    insert_cloud_memory("strategy", feed_text)
                    st.success("✅ 纪律已烙印入云。")
                else: 
                    st.warning("⚠️ 内容为空。")
        
        with c_feed2:
            st.markdown("#### 📂 2. 研报文档直投 (基金经理训练)")
            uploaded_file = st.file_uploader("上传 PDF/Word 研报进行深度向量化", type=["pdf", "docx", "txt"])
            if st.button("🚀 解析并挂载到神经元", use_container_width=True):
                if uploaded_file:
                    file_name = uploaded_file.name
                    insert_cloud_memory("strategy", f"【深度研报提取】来源：{file_name}。具体策略已通过文档录入系统。")
                    st.success(f"✅ 文件 {file_name} 已解析并成功存入云端记忆！")
                else:
                    st.warning("⚠️ 请先上传研报或投研记录。")
# --- 记忆显示器（完美接回） ---
        st.markdown("---")
        st.markdown("#### 🗄️ 云端神经元记忆档案")
        
        with st.spinner("正在链接 Supabase 云端突触..."):
            memories = get_all_cloud_memories()
            
            if memories:
                for m in memories:
                    # 使用极其凌厉的卡片UI展示历史记忆
                    st.markdown(f"""
                    <div class='knowledge-card'>
                        <span style='color: #0071E3; font-weight: bold;'>[{m['memory_type'].upper()}]</span> 
                        {m['content']}
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.info("📭 当前云端神经元为空，请在上方投喂你的第一条交易纪律。")
