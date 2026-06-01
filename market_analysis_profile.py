from __future__ import annotations

from collections.abc import Mapping
from numbers import Number
from typing import Any


MARKET_A_SHARE = "A股"
MARKET_US_STOCK = "美股"
MARKET_ETF = "ETF"
MARKET_HK_STOCK = "港股"
MARKET_JP_STOCK = "日股"
MARKET_UNKNOWN = "未知"

SOURCE = "rule-based market profile"

_A_SHARE_SUFFIXES = (".SH", ".SZ", ".SS", ".BJ")
_ETF_NAME_KEYWORDS = ("ETF", "交易型开放式", "基金", "QDII", "LOF")
_SH_ETF_PREFIXES = ("510", "511", "512", "513", "515", "516", "518", "560", "561", "562", "563", "588")
_SZ_ETF_PREFIXES = ("159", "160", "161", "162", "163", "164")


def _as_mapping(value: Any) -> dict:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _to_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip() or default
    if isinstance(value, (bool, Number)):
        return str(value)
    return str(value).strip() or default


def _upper_text(value: Any) -> str:
    return _to_text(value).upper()


def _ticker_core(ticker: Any) -> str:
    text = _upper_text(ticker)
    if "." in text:
        return text.split(".", 1)[0]
    return text


def _has_etf_hint(*values: Any) -> bool:
    text = " ".join(_upper_text(value) for value in values if _to_text(value))
    return any(keyword.upper() in text for keyword in _ETF_NAME_KEYWORDS)


def is_a_share_etf_ticker(ticker: Any) -> bool:
    text = _upper_text(ticker)
    core = _ticker_core(text)
    if not core.isdigit() or len(core) != 6:
        return False
    if text.endswith(".SH") or text.endswith(".SS"):
        return core.startswith(_SH_ETF_PREFIXES)
    if text.endswith(".SZ"):
        return core.startswith(_SZ_ETF_PREFIXES)
    return core.startswith(_SH_ETF_PREFIXES + _SZ_ETF_PREFIXES)


def identify_market_type(
    ticker: Any = "",
    name: Any = "",
    asset_type: Any = "",
    fund_type: Any = "",
    packet: Any = None,
) -> str:
    payload = _as_mapping(packet)
    ticker_text = _upper_text(ticker or payload.get("ticker") or payload.get("code") or payload.get("symbol"))
    name_text = _to_text(name or payload.get("name") or payload.get("security_name") or payload.get("fund_name"))
    asset_text = _to_text(asset_type or payload.get("asset_type") or payload.get("type") or payload.get("category"))
    fund_text = _to_text(fund_type or payload.get("fund_type") or payload.get("fund_category"))

    if _has_etf_hint(name_text, asset_text, fund_text) or is_a_share_etf_ticker(ticker_text):
        return MARKET_ETF
    if ticker_text.endswith(_A_SHARE_SUFFIXES) or (ticker_text.isdigit() and len(ticker_text) == 6):
        return MARKET_A_SHARE
    if ticker_text.endswith(".HK"):
        return MARKET_HK_STOCK
    if ticker_text.endswith(".T") or ticker_text.endswith(".JP"):
        return MARKET_JP_STOCK
    if ticker_text.replace("-", "").replace(".", "").isalpha() and ticker_text:
        return MARKET_US_STOCK
    return MARKET_UNKNOWN


def _method(
    name: str,
    fit: str,
    evidence_focus: list[str],
    risk_focus: list[str],
    action_hint: str,
) -> dict:
    return {
        "name": name,
        "fit": fit,
        "evidence_focus": list(evidence_focus),
        "risk_focus": list(risk_focus),
        "action_hint": action_hint,
    }


def _a_share_profile() -> dict:
    return {
        "market": MARKET_A_SHARE,
        "label": "A股个股",
        "data_source_priority": ["Tushare", "AkShare补充", "yfinance fallback", "本地缓存"],
        "core_features": ["涨跌停", "龙虎榜", "融资融券", "公告", "题材", "资金流", "ST/停牌", "北交所/科创/创业板差异"],
        "indicator_focus": ["MA20/MA60", "涨停强度", "成交额", "资金流", "公告风险", "减持/质押"],
        "risk_focus": ["政策/监管", "流动性", "涨跌停", "减持/质押", "公告缺口"],
        "methods": [
            _method("趋势跟踪", "核心", ["MA20/MA60", "阶段位置", "成交额"], ["跌破均线", "缩量反抽"], "只在趋势和纪律同向时考虑试探。"),
            _method("Stage Analysis", "核心", ["中期均线", "底部/二阶段/顶部判断"], ["三/四阶段转弱"], "优先过滤非二阶段标的。"),
            _method("CAN SLIM / 机构成长股", "辅助", ["业绩增速", "题材景气", "机构参与"], ["业绩真空", "估值透支"], "没有业绩和题材证据时只观察。"),
            _method("VCP / 波动收敛突破", "核心", ["缩量收敛", "突破量能", "压力位"], ["假突破", "追高"], "突破后仍需回撤不破或放量确认。"),
            _method("相对强弱 RS / 行业轮动", "核心", ["板块强度", "同业排名", "指数比较"], ["板块退潮"], "弱于板块时不主动加仓。"),
            _method("量价结构", "核心", ["放量/缩量", "涨停强度", "换手"], ["高位放量滞涨"], "量价不一致时降级为待验证。"),
            _method("资金流 / 机构行为", "核心", ["资金流", "龙虎榜", "融资融券"], ["游资一日游", "融资过热"], "资金证据缺失时不扩大仓位。"),
            _method("风险预算 / 仓位管理", "核心", ["最大回撤", "现金缓冲", "单票暴露"], ["满仓", "融资追高"], "先定义失效线，再讨论加仓。"),
            _method("事件驱动 / 财报 / 公告", "核心", ["公告", "减持/质押", "业绩预告"], ["监管问询", "黑天鹅公告"], "公告风险未读完前不追。"),
            _method("宏观流动性 / 利率 / 汇率", "辅助", ["政策流动性", "汇率", "北向/风险偏好"], ["政策收紧"], "只作为仓位环境，不替代个股证据。"),
            _method("ETF 赛道配置", "不适用", ["行业 ETF 可作对照"], ["把个股当 ETF 配置"], "个股不直接套用 ETF 权重。"),
        ],
    }


def _us_stock_profile() -> dict:
    return {
        "market": MARKET_US_STOCK,
        "label": "美股个股",
        "data_source_priority": ["yfinance", "财报/SEC资料缓存", "行业指数缓存", "本地缓存"],
        "core_features": ["财报", "EPS/Revenue growth", "行业相对强弱", "行业轮动", "宏观利率", "美元", "美债", "盘前盘后", "无涨跌停"],
        "indicator_focus": ["相对强弱", "RS", "成交量", "财报后 gap", "52周新高", "指数/行业比较"],
        "risk_focus": ["财报/指引", "估值", "宏观利率", "汇率", "盘后跳空"],
        "methods": [
            _method("趋势跟踪", "核心", ["均线趋势", "52周新高", "成交量"], ["财报后跳空反转"], "趋势未破且大盘配合时才考虑试探。"),
            _method("Stage Analysis", "核心", ["Stage 2 趋势", "指数相对表现"], ["Stage 3/4"], "避开分发和下跌阶段。"),
            _method("CAN SLIM / 机构成长股", "核心", ["EPS/Revenue growth", "新产品", "机构需求"], ["估值压缩", "指引下修"], "财报和指引未确认前不放大仓位。"),
            _method("VCP / 波动收敛突破", "核心", ["波动收敛", "pivot", "突破量"], ["假突破", "财报窗口"], "突破应避开未定价财报风险。"),
            _method("相对强弱 RS / 行业轮动", "核心", ["RS", "行业轮动", "指数比较"], ["行业退潮"], "强于行业和指数才进入候选优先级。"),
            _method("量价结构", "核心", ["成交量", "gap", "机构吸筹"], ["放量下跌"], "量价背离时不追。"),
            _method("资金流 / 机构行为", "辅助", ["成交量", "期权/13F后续扩展"], ["期权噪音", "盘后跳空"], "不用 A股龙虎榜口径判断美股。"),
            _method("风险预算 / 仓位管理", "核心", ["波动率", "财报窗口", "最大回撤"], ["隔夜风险", "汇率风险"], "财报前控制单票暴露。"),
            _method("事件驱动 / 财报 / 公告", "核心", ["财报", "指引", "分析师修正"], ["指引下修", "监管事件"], "财报事件优先于短线形态。"),
            _method("宏观流动性 / 利率 / 汇率", "核心", ["美债收益率", "美元", "风险偏好"], ["利率上行", "美元波动"], "宏观逆风时降低估值敏感仓位。"),
            _method("ETF 赛道配置", "不适用", ["行业 ETF 可作 beta 参照"], ["把单股当赛道配置"], "个股不直接套用 ETF 资金比例。"),
        ],
    }


def _etf_profile() -> dict:
    return {
        "market": MARKET_ETF,
        "label": "ETF / 基金",
        "data_source_priority": ["Tushare ETF", "fund_daily", "etf_basic", "fund holdings", "本地ETF池"],
        "core_features": ["跟踪指数", "费率", "成交额", "溢价折价", "持仓重叠", "主题分类"],
        "indicator_focus": ["流动性", "跟踪指数", "20/60日趋势", "同赛道比较", "过热/回踩"],
        "risk_focus": ["追高", "同类重复配置", "流动性不足", "QDII/跨境汇率"],
        "methods": [
            _method("趋势跟踪", "核心", ["20/60日趋势", "赛道强弱"], ["高位回撤"], "只在赛道趋势和风险预算允许时配置。"),
            _method("Stage Analysis", "辅助", ["赛道阶段", "指数位置"], ["主题退潮"], "避免在退潮阶段摊大仓位。"),
            _method("CAN SLIM / 机构成长股", "不适用", ["成分股成长可作背景"], ["把 ETF 当个股财报"], "ETF 不用单股 CAN SLIM 直接打分。"),
            _method("VCP / 波动收敛突破", "辅助", ["箱体收敛", "指数突破"], ["主题假突破"], "突破后仍需看赛道和成交额。"),
            _method("相对强弱 RS / 行业轮动", "核心", ["同赛道比较", "指数比较", "行业轮动"], ["轮动退潮"], "强赛道优先，弱赛道只观察。"),
            _method("量价结构", "核心", ["成交额", "换手", "回踩"], ["流动性不足"], "成交额不足时降低可执行级别。"),
            _method("资金流 / 机构行为", "辅助", ["份额变化", "成交额", "融资适配"], ["拥挤交易"], "资金过热时不追高。"),
            _method("风险预算 / 仓位管理", "核心", ["现金缓冲", "融资比例", "相关性"], ["重复配置", "杠杆过高"], "ETF 是仓位工具，不是满仓理由。"),
            _method("事件驱动 / 财报 / 公告", "辅助", ["指数调整", "成分股事件", "基金公告"], ["停牌/折溢价异常"], "跨境/QDII 需额外看汇率和额度。"),
            _method("宏观流动性 / 利率 / 汇率", "核心", ["利率", "汇率", "流动性"], ["QDII汇率", "利率冲击"], "宏观不利时降低主题 ETF 暴露。"),
            _method("ETF 赛道配置", "核心", ["跟踪指数", "持仓重叠", "主题轮动", "流动性"], ["同类重复", "追高"], "按赛道和相关性分组，而不是堆同类 ETF。"),
        ],
    }


def _generic_profile(market_type: str) -> dict:
    return {
        "market": market_type or MARKET_UNKNOWN,
        "label": "通用资产",
        "data_source_priority": ["本地缓存", "后续按市场扩展"],
        "core_features": ["趋势", "成交量", "风险预算", "事件风险"],
        "indicator_focus": ["趋势", "量价", "相对强弱", "最大回撤"],
        "risk_focus": ["数据缺口", "流动性", "事件风险"],
        "methods": [
            _method("趋势跟踪", "待适配", ["趋势数据"], ["数据缺口"], "先确认市场类型。"),
            _method("风险预算 / 仓位管理", "核心", ["现金缓冲", "最大回撤"], ["仓位过高"], "市场类型不明时只观察。"),
        ],
    }


def get_market_analysis_profile(
    market_type: Any = None,
    ticker: Any = "",
    name: Any = "",
    packet: Any = None,
) -> dict:
    market = _to_text(market_type)
    if not market or market in {"auto", "AUTO", MARKET_UNKNOWN}:
        market = identify_market_type(ticker=ticker, name=name, packet=packet)
    if market in {MARKET_ETF, "A股ETF", "ETF/基金"}:
        profile = _etf_profile()
    elif market in {MARKET_A_SHARE, "A_SHARE", "A股个股"}:
        profile = _a_share_profile()
    elif market in {MARKET_US_STOCK, "US", "US_STOCK", "美股个股"}:
        profile = _us_stock_profile()
    else:
        profile = _generic_profile(market)
    profile["source"] = SOURCE
    profile["deepseek_called"] = False
    return profile
