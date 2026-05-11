import math

import numpy as np
import pandas as pd


DEFAULT_RULES = {
    "ma_fast": 5,
    "ma_mid": 20,
    "ma_slow": 60,
    "rsi_period": 14,
    "rsi_buy_max": 58,
    "rsi_sell_min": 74,
    "stop_loss_pct": 0.08,
    "take_profit_pct": 0.18,
    "max_drawdown_exit": 0.12,
    "position_size": 1.0,
    "mode": "default",
}


BACKTEST_MODES = {
    "default": "默认纪律",
    "free": "自由趋势",
    "dynamic": "动态止盈止损",
}


def normalize_price_frame(price_df):
    if price_df is None or price_df.empty:
        return pd.DataFrame()

    df = price_df.copy()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [str(col[0] or col[-1]) for col in df.columns]

    rename_map = {
        "Date": "date",
        "Datetime": "date",
        "日期": "date",
        "时间": "date",
        "Open": "open",
        "开盘": "open",
        "High": "high",
        "最高": "high",
        "Low": "low",
        "最低": "low",
        "Close": "close",
        "收盘": "close",
        "Volume": "volume",
        "成交量": "volume",
        "Amount": "amount",
        "成交额": "amount",
        "Turnover": "turnover_rate",
        "换手率": "turnover_rate",
    }
    df = df.rename(columns={c: rename_map.get(str(c), str(c).lower()) for c in df.columns})
    if "date" not in df.columns:
        df = df.reset_index()
        df = df.rename(columns={c: rename_map.get(str(c), str(c).lower()) for c in df.columns})
        if "date" not in df.columns and "index" in df.columns:
            df = df.rename(columns={"index": "date"})

    if "date" not in df.columns:
        return pd.DataFrame()

    for col in ["open", "high", "low", "close", "volume", "amount", "turnover_rate"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date", "close"]).sort_values("date").reset_index(drop=True)
    return df


def compute_rsi(close, period=14):
    if close is None or len(close) < period + 2:
        return pd.Series(index=close.index if close is not None else [], dtype=float)
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def add_indicators(price_df, rules=None):
    df = normalize_price_frame(price_df)
    if df.empty:
        return df

    rules = {**DEFAULT_RULES, **(rules or {})}
    close = df["close"]
    df["ma_fast"] = close.rolling(int(rules["ma_fast"])).mean()
    df["ma_mid"] = close.rolling(int(rules["ma_mid"])).mean()
    df["ma_slow"] = close.rolling(int(rules["ma_slow"])).mean()
    df["rsi"] = compute_rsi(close, int(rules["rsi_period"]))
    df["daily_return"] = close.pct_change().fillna(0)
    df["rolling_peak"] = close.cummax()
    df["drawdown_from_peak"] = close / df["rolling_peak"] - 1
    if {"high", "low", "close"}.issubset(df.columns):
        prev_close = df["close"].shift(1)
        tr = pd.concat([
            df["high"] - df["low"],
            (df["high"] - prev_close).abs(),
            (df["low"] - prev_close).abs(),
        ], axis=1).max(axis=1)
        df["atr_14"] = tr.rolling(14).mean()
        df["atr_pct"] = df["atr_14"] / df["close"].replace(0, np.nan)
    else:
        df["atr_14"] = np.nan
        df["atr_pct"] = np.nan
    df["volatility_20"] = close.pct_change().rolling(20).std()
    if "volume" in df.columns:
        df["volume_ratio_20"] = df["volume"] / df["volume"].rolling(20).mean().replace(0, np.nan)
    else:
        df["volume_ratio_20"] = np.nan
    return df


def generate_signals(price_df, rules=None, cost_price=None):
    df = add_indicators(price_df, rules)
    if df.empty:
        return df

    rules = {**DEFAULT_RULES, **(rules or {})}
    mode = rules.get("mode", "default")
    cost = _num(cost_price)
    in_position = False
    entry_price = None
    peak_since_entry = None
    signals = []
    reasons = []

    for _, row in df.iterrows():
        close = _num(row.get("close"))
        ma_mid = _num(row.get("ma_mid"))
        ma_slow = _num(row.get("ma_slow"))
        rsi = _num(row.get("rsi"))
        atr_pct = _num(row.get("atr_pct"))
        vol_pct = _num(row.get("volatility_20"))
        signal = "HOLD" if in_position else "WAIT"
        reason = "等待有效信号"

        if close is None:
            signals.append(signal)
            reasons.append(reason)
            continue

        if in_position:
            peak_since_entry = max(peak_since_entry or close, close)
            stop_anchor = entry_price or cost or close
            dynamic_stop, dynamic_take = _dynamic_risk_pct(row, rules)
            if mode == "dynamic":
                stop_pct = dynamic_stop
                take_pct = dynamic_take
                trailing_limit = max(float(rules["max_drawdown_exit"]), dynamic_stop * 1.2)
            else:
                stop_pct = float(rules["stop_loss_pct"])
                take_pct = float(rules["take_profit_pct"])
                trailing_limit = float(rules["max_drawdown_exit"])

            stop_loss = stop_anchor * (1 - stop_pct)
            take_profit = stop_anchor * (1 + take_pct)
            trailing_dd = close / max(peak_since_entry, 1) - 1

            if mode == "free":
                if ma_slow is not None and close < ma_slow and (rsi is None or rsi < 52):
                    signal = "SELL"
                    reason = "自由模式：跌破慢线，趋势失效"
                elif ma_mid is not None and close < ma_mid and rsi is not None and rsi < 45:
                    signal = "REDUCE"
                    reason = "自由模式：跌破中线且动能转弱"
                elif rsi is not None and rsi >= float(rules["rsi_sell_min"]) and ma_mid is not None and close < ma_mid:
                    signal = "REDUCE"
                    reason = "自由模式：高RSI后跌回中线，先降风险"
            else:
                if close <= stop_loss:
                    signal = "SELL"
                    reason = f"{BACKTEST_MODES.get(mode, '默认纪律')}：跌破{'动态' if mode == 'dynamic' else '固定'}止损线"
                elif close >= take_profit and (rsi is None or rsi >= 60):
                    signal = "TAKE_PROFIT"
                    reason = f"{BACKTEST_MODES.get(mode, '默认纪律')}：达到{'动态' if mode == 'dynamic' else '固定'}止盈区"
                elif trailing_dd <= -trailing_limit:
                    signal = "SELL"
                    reason = "持仓后回撤超过纪律阈值"
                elif ma_slow is not None and close < ma_slow and rsi is not None and rsi < 45:
                    signal = "REDUCE"
                    reason = "跌破慢线且动能偏弱"
        else:
            trend_ok = ma_mid is not None and ma_slow is not None and close >= ma_mid >= ma_slow
            cost_ok = True
            if cost:
                cost_ok = close <= cost * 1.03
            rsi_ok = rsi is None or rsi <= float(rules["rsi_buy_max"])
            if mode == "free":
                rsi_ok = rsi is None or rsi <= max(float(rules["rsi_buy_max"]), 66)
            if trend_ok and rsi_ok and cost_ok:
                signal = "BUY"
                reason = "趋势站稳且未明显过热"
            elif mode != "free" and cost and close <= cost * (1 - float(rules["stop_loss_pct"])):
                signal = "AVOID"
                reason = "低于参考成本且未确认止跌"

        if signal == "BUY":
            in_position = True
            entry_price = close
            peak_since_entry = close
        elif signal in {"SELL", "TAKE_PROFIT"}:
            in_position = False
            entry_price = None
            peak_since_entry = None

        signals.append(signal)
        reasons.append(reason)

    df["signal"] = signals
    df["signal_reason"] = reasons
    df["mode"] = mode
    return df


def _dynamic_risk_pct(row, rules):
    atr_pct = _num(row.get("atr_pct"))
    vol_pct = _num(row.get("volatility_20"))
    base_vol = atr_pct if atr_pct is not None and atr_pct > 0 else vol_pct
    if base_vol is None or base_vol <= 0:
        return float(rules["stop_loss_pct"]), float(rules["take_profit_pct"])
    stop_pct = min(0.18, max(0.04, base_vol * 1.8))
    take_pct = min(0.45, max(0.08, base_vol * 3.2))
    return float(stop_pct), float(take_pct)


def simulate_trades(signal_df, initial_cash=100000, position_size=1.0, fee_rate=0.0005):
    if signal_df is None or signal_df.empty:
        return pd.DataFrame(), pd.DataFrame()

    cash = float(initial_cash)
    shares = 0.0
    entry_price = None
    trades = []
    equity_rows = []
    position_size = max(0.0, min(float(position_size), 1.0))

    for _, row in signal_df.iterrows():
        date = row.get("date")
        close = _num(row.get("close"))
        signal = row.get("signal", "WAIT")
        reason = row.get("signal_reason", "")
        if close is None:
            continue

        if signal == "BUY" and shares <= 0 and cash > 0:
            budget = cash * position_size
            shares = budget * (1 - fee_rate) / close
            cash -= budget
            entry_price = close
            trades.append({
                "date": date,
                "action": "BUY",
                "price": round(close, 4),
                "shares": round(shares, 4),
                "reason": reason,
                "pnl_pct": "",
            })
        elif signal in {"SELL", "TAKE_PROFIT"} and shares > 0:
            proceeds = shares * close * (1 - fee_rate)
            pnl_pct = (close / entry_price - 1) * 100 if entry_price else 0
            cash += proceeds
            trades.append({
                "date": date,
                "action": signal,
                "price": round(close, 4),
                "shares": round(shares, 4),
                "reason": reason,
                "pnl_pct": round(pnl_pct, 2),
            })
            shares = 0.0
            entry_price = None
        elif signal == "REDUCE" and shares > 0:
            sell_shares = shares * 0.5
            proceeds = sell_shares * close * (1 - fee_rate)
            pnl_pct = (close / entry_price - 1) * 100 if entry_price else 0
            cash += proceeds
            shares -= sell_shares
            trades.append({
                "date": date,
                "action": "REDUCE",
                "price": round(close, 4),
                "shares": round(sell_shares, 4),
                "reason": reason,
                "pnl_pct": round(pnl_pct, 2),
            })

        equity = cash + shares * close
        equity_rows.append({
            "date": date,
            "close": close,
            "cash": cash,
            "shares": shares,
            "equity": equity,
            "signal": signal,
        })

    return pd.DataFrame(equity_rows), pd.DataFrame(trades)


def compute_backtest_metrics(equity_curve, trades=None, initial_cash=100000):
    if equity_curve is None or equity_curve.empty:
        return {
            "total_return_pct": 0,
            "annual_return_pct": 0,
            "sharpe": 0,
            "max_drawdown_pct": 0,
            "win_rate_pct": 0,
            "trade_count": 0,
        }

    equity = equity_curve["equity"].astype(float)
    total_return = equity.iloc[-1] / float(initial_cash) - 1
    daily = equity.pct_change().dropna()
    days = max(len(equity_curve), 1)
    annual_return = (1 + total_return) ** (252 / days) - 1 if total_return > -1 else -1
    sharpe = 0
    if len(daily) > 2 and daily.std() > 0:
        sharpe = daily.mean() / daily.std() * math.sqrt(252)
    dd = equity / equity.cummax() - 1

    trade_count = 0
    win_rate = 0
    if trades is not None and not trades.empty:
        exits = trades[trades["action"].isin(["SELL", "TAKE_PROFIT", "REDUCE"])]
        trade_count = len(exits)
        pnl = pd.to_numeric(exits.get("pnl_pct"), errors="coerce").dropna()
        if len(pnl):
            win_rate = (pnl > 0).mean() * 100

    return {
        "total_return_pct": round(float(total_return * 100), 2),
        "annual_return_pct": round(float(annual_return * 100), 2),
        "sharpe": round(float(sharpe), 2),
        "max_drawdown_pct": round(float(dd.min() * 100), 2),
        "win_rate_pct": round(float(win_rate), 2),
        "trade_count": int(trade_count),
    }


def build_cost_context(price_df, cost_price=None, current_price=None):
    df = normalize_price_frame(price_df)
    latest = _num(current_price)
    if latest is None and not df.empty:
        latest = _num(df["close"].iloc[-1])
    cost = _num(cost_price)
    pnl_pct = None
    state = "未输入成本价"
    if latest and cost and cost > 0:
        pnl_pct = round((latest / cost - 1) * 100, 2)
        state = f"浮盈 {pnl_pct}%" if pnl_pct > 0 else ("接近成本" if pnl_pct == 0 else f"浮亏 {abs(pnl_pct)}%")
    return {
        "cost_price": cost,
        "current_price": latest,
        "pnl_pct": pnl_pct,
        "state": state,
    }


def run_backtest(price_df, rules=None, cost_price=None, initial_cash=100000, mode=None):
    rules = {**DEFAULT_RULES, **(rules or {})}
    if mode:
        rules["mode"] = mode
    mode = rules.get("mode", "default")
    signal_df = generate_signals(price_df, rules=rules, cost_price=cost_price)
    equity_curve, trades = simulate_trades(
        signal_df,
        initial_cash=initial_cash,
        position_size=rules.get("position_size", 1.0),
    )
    metrics = compute_backtest_metrics(equity_curve, trades=trades, initial_cash=initial_cash)
    cost_context = build_cost_context(price_df, cost_price=cost_price)
    latest_signal = build_latest_signal(signal_df, cost_context, metrics)
    signal_counts = signal_df["signal"].value_counts().to_dict() if "signal" in signal_df.columns else {}
    trader_brief = build_trader_brief(signal_df, trades, metrics, cost_context, latest_signal, rules)
    return {
        "mode": mode,
        "mode_label": BACKTEST_MODES.get(mode, mode),
        "signals": signal_df,
        "equity_curve": equity_curve,
        "trades": trades,
        "metrics": metrics,
        "rules": rules,
        "position_context": cost_context,
        "latest_signal": latest_signal,
        "signal_counts": signal_counts,
        "data_points": int(len(signal_df)),
        "trader_brief": trader_brief,
        "summary": trader_brief.get("plain_summary") or build_report_summary(metrics, cost_context, latest_signal),
    }


def run_multi_mode_backtests(price_df, base_rules=None, cost_price=None, initial_cash=100000, modes=None):
    modes = modes or ["default", "free", "dynamic"]
    reports = {}
    for mode in modes:
        rules = {**DEFAULT_RULES, **(base_rules or {}), "mode": mode}
        reports[mode] = run_backtest(
            price_df,
            rules=rules,
            cost_price=cost_price,
            initial_cash=initial_cash,
            mode=mode,
        )
    return {
        "reports": reports,
        "summary": build_multi_mode_summary(reports),
    }


def build_multi_mode_summary(reports):
    usable = []
    for mode, report in (reports or {}).items():
        metrics = report.get("metrics", {})
        trade_count = int(metrics.get("trade_count", 0) or 0)
        total = _num(metrics.get("total_return_pct"), 0) or 0
        dd = _num(metrics.get("max_drawdown_pct"), 0) or 0
        sharpe = _num(metrics.get("sharpe"), 0) or 0
        usable.append({
            "mode": mode,
            "label": report.get("mode_label", mode),
            "trade_count": trade_count,
            "total": total,
            "dd": dd,
            "sharpe": sharpe,
        })

    traded = [row for row in usable if row["trade_count"] > 0]
    if not traded:
        return "三种模式在当前区间都没有形成可验证交易，只能参考趋势状态，不能用收益率判断优劣。"

    best_return = max(traded, key=lambda row: row["total"])
    best_risk = max(traded, key=lambda row: (row["dd"], row["sharpe"]))
    parts = [
        f"收益最好：{best_return['label']}（{best_return['total']}%）",
        f"回撤控制较好：{best_risk['label']}（最大回撤 {best_risk['dd']}%）",
    ]
    if best_return["mode"] != best_risk["mode"]:
        parts.append("收益和风控不是同一个模式，说明这只票需要在进攻和防守之间取舍。")
    else:
        parts.append("同一模式同时兼顾收益和回撤，可优先作为参考。")
    return "；".join(parts)


def build_latest_signal(signal_df, cost_context, metrics):
    if signal_df is None or signal_df.empty:
        return {
            "action": "数据不足",
            "reason": "没有可用行情生成回测信号",
            "date": "",
            "price": None,
        }

    latest = signal_df.iloc[-1]
    raw_signal = latest.get("signal", "WAIT")
    reason = latest.get("signal_reason", "")
    current = _num(latest.get("close"))
    cost = cost_context.get("cost_price")
    pnl_pct = cost_context.get("pnl_pct")
    max_dd = _num(metrics.get("max_drawdown_pct"), 0) or 0

    if raw_signal in {"BUY"}:
        action = "小仓尝试"
    elif raw_signal in {"SELL"}:
        action = "止损/退出"
    elif raw_signal in {"TAKE_PROFIT"}:
        action = "分批止盈"
    elif raw_signal in {"REDUCE"}:
        action = "减仓"
    elif raw_signal in {"AVOID"}:
        action = "禁止开仓"
    else:
        action = "继续观察"

    if cost and current:
        if pnl_pct is not None and pnl_pct <= -8:
            reason = f"{reason}；当前相对成本浮亏 {abs(pnl_pct)}%，优先检查止损纪律"
        elif pnl_pct is not None and pnl_pct >= 15:
            reason = f"{reason}；当前相对成本浮盈 {pnl_pct}%，优先检查移动止盈"

    if max_dd <= -20 and action in {"小仓尝试", "继续观察"}:
        reason = f"{reason}；该策略历史最大回撤较深，仓位需降档"

    return {
        "action": action,
        "raw_signal": raw_signal,
        "reason": reason,
        "date": str(latest.get("date").date()) if pd.notna(latest.get("date")) else "",
        "price": round(current, 4) if current is not None else None,
    }


def build_report_summary(metrics, cost_context, latest_signal=None):
    state = cost_context.get("state", "未输入成本价")
    total = metrics.get("total_return_pct", 0)
    dd = metrics.get("max_drawdown_pct", 0)
    sharpe = metrics.get("sharpe", 0)
    action = (latest_signal or {}).get("action", "继续观察")
    if total > 0 and sharpe >= 1:
        stance = "策略历史表现较稳"
    elif dd <= -18:
        stance = "策略回撤偏大，需降低仓位"
    elif total <= 0:
        stance = "策略历史收益不足，优先观察"
    else:
        stance = "策略可作为辅助参考"
    return f"{stance}；最新信号：{action}；当前相对成本状态：{state}；回测收益 {total}%、最大回撤 {dd}%、夏普 {sharpe}。"


def build_trader_brief(signal_df, trades, metrics, cost_context, latest_signal, rules):
    data_points = int(len(signal_df)) if signal_df is not None else 0
    trade_count = int(metrics.get("trade_count", 0) or 0)
    ma_slow = int(_num(rules.get("ma_slow"), 60) or 60)
    required_points = max(ma_slow + 40, 120)
    warnings = []
    next_steps = []
    mode = rules.get("mode", "default")
    mode_label = BACKTEST_MODES.get(mode, mode)

    if data_points < required_points:
        warnings.append(f"样本只有 {data_points} 个交易日，慢线是 {ma_slow} 日，样本偏短。")
        next_steps.append("把回测起点拉到近两年，或把慢线改成60日。")

    if trade_count == 0:
        verdict = "这次没有形成可验证交易"
        action = "先不要按这个回测下结论"
        explanation = f"{mode_label}在当前区间没有触发买入/卖出。它不是在说这只股票一定不好，而是这组规则没有形成可验证样本，收益、胜率、夏普为0没有统计意义。"
        warnings.append("交易次数为0，不能用收益率判断规则好坏。")
        next_steps.append("换成“持仓体检（推荐）”或“短线试错”，再跑一次。")
    else:
        total = _num(metrics.get("total_return_pct"), 0) or 0
        dd = _num(metrics.get("max_drawdown_pct"), 0) or 0
        sharpe = _num(metrics.get("sharpe"), 0) or 0
        if total > 0 and sharpe >= 0.8 and dd > -18:
            verdict = "规则历史表现可参考"
            action = latest_signal.get("action", "继续观察")
            explanation = f"{mode_label}在历史区间里有交易、有收益，且回撤没有明显失控，可作为辅助判断。"
        elif dd <= -22:
            verdict = "规则回撤偏大"
            action = "降仓/只观察"
            explanation = f"{mode_label}历史上可能让账户承受较深回撤，不适合作为重仓依据。"
            warnings.append(f"最大回撤 {dd}% 偏深。")
            next_steps.append("降低单次仓位，或提高止损纪律后重跑。")
        elif total <= 0:
            verdict = "规则历史收益不足"
            action = "只观察"
            explanation = f"{mode_label}在当前样本中没有证明优势，不适合直接拿来指导买入。"
            next_steps.append("换更长区间或更贴近该股性格的规则。")
        else:
            verdict = "规则只能辅助参考"
            action = latest_signal.get("action", "继续观察")
            explanation = f"{mode_label}有一定参考价值，但收益质量还不够强，需要结合趋势和资金面。"

    if mode == "free":
        next_steps.append("自由趋势模式不靠固定止盈止损，适合观察趋势能否延续，但回撤可能更大。")
    elif mode == "dynamic":
        next_steps.append("动态模式会随波动调整止盈止损，通常更贴合高波动股票，但可能提前卖飞。")
    else:
        next_steps.append("默认模式纪律清晰，适合检查固定止损止盈是否适合这只票。")

    if cost_context.get("pnl_pct") is not None:
        pnl = cost_context.get("pnl_pct")
        if pnl >= 15:
            next_steps.append("你现在相对成本浮盈较高，优先检查移动止盈，而不是追加买入。")
        elif pnl <= -8:
            next_steps.append("你现在相对成本浮亏较深，优先检查止损线是否失效。")

    if not next_steps:
        next_steps.append("看最新信号、止损线和资金面是否共振。")

    warnings = list(dict.fromkeys(warnings))[:5]
    next_steps = list(dict.fromkeys(next_steps))[:5]
    plain_summary = f"{verdict}：{explanation} 当前建议：{action}。"
    return {
        "verdict": verdict,
        "action": action,
        "explanation": explanation,
        "warnings": warnings,
        "next_steps": next_steps,
        "plain_summary": plain_summary,
        "sample_days": data_points,
        "required_days": required_points,
    }


def compact_report_for_prompt(report, max_trades=8):
    if not report:
        return {}

    trades = report.get("trades")
    if trades is not None and not trades.empty:
        trade_rows = trades.tail(max_trades).copy()
        if "date" in trade_rows.columns:
            trade_rows["date"] = trade_rows["date"].astype(str)
        trade_rows = trade_rows.to_dict("records")
    else:
        trade_rows = []

    return {
        "summary": report.get("summary", ""),
        "metrics": report.get("metrics", {}),
        "position_context": report.get("position_context", {}),
        "latest_signal": report.get("latest_signal", {}),
        "trader_brief": report.get("trader_brief", {}),
        "rules": report.get("rules", {}),
        "signal_counts": report.get("signal_counts", {}),
        "data_points": report.get("data_points", 0),
        "recent_trades": trade_rows,
    }


def _num(value, default=None):
    try:
        if value is None or value == "":
            return default
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default
