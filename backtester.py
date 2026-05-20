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
    "tech_rsi_buy_max": 68,
    "tech_rsi_extreme": 78,
    "tech_reduce_gap_days": 5,
    "tech_max_reduce_count": 3,
    "tech_trailing_drawdown_pct": 0.12,
    "tech_atr_multiplier": 2.5,
    "tech_volume_min_ratio": 0.6,
    "tech_break_volume_ratio": 1.3,
    "tech_big_drop_pct": 0.06,
}


BACKTEST_MODES = {
    "default": "默认纪律",
    "free": "自由趋势",
    "dynamic": "动态止盈止损",
    "tech_growth": "科技成长股",
}


BACKTEST_MODE_ORDER = ["default", "free", "dynamic", "tech_growth"]


TECH_GROWTH_STOCK_POOL = [
    {"ts_code": "002008.SZ", "name": "大族激光"},
    {"ts_code": "002837.SZ", "name": "英维克"},
    {"ts_code": "601138.SH", "name": "工业富联"},
    {"ts_code": "002158.SZ", "name": "汉钟精机"},
    {"ts_code": "002335.SZ", "name": "科华数据"},
    {"ts_code": "603986.SH", "name": "兆易创新"},
    {"ts_code": "300308.SZ", "name": "中际旭创"},
    {"ts_code": "300394.SZ", "name": "天孚通信"},
    {"ts_code": "688981.SH", "name": "中芯国际"},
    {"ts_code": "300750.SZ", "name": "宁德时代"},
]


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
    peak_rsi_since_entry = None
    last_reduce_idx = None
    reduce_count_since_entry = 0
    big_down_streak = 0
    signals = []
    reasons = []

    for row_idx, row in df.iterrows():
        close = _num(row.get("close"))
        ma_mid = _num(row.get("ma_mid"))
        ma_slow = _num(row.get("ma_slow"))
        rsi = _num(row.get("rsi"))
        atr_pct = _num(row.get("atr_pct"))
        vol_pct = _num(row.get("volatility_20"))
        daily_return = _num(row.get("daily_return"), 0) or 0
        volume_ratio = _num(row.get("volume_ratio_20"))
        signal = "HOLD" if in_position else "WAIT"
        reason = "等待有效信号"

        if close is None:
            signals.append(signal)
            reasons.append(reason)
            continue

        if daily_return <= -float(rules.get("tech_big_drop_pct", 0.06)):
            big_down_streak += 1
        else:
            big_down_streak = 0

        if in_position:
            peak_since_entry = max(peak_since_entry or close, close)
            if rsi is not None:
                peak_rsi_since_entry = max(peak_rsi_since_entry or rsi, rsi)
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
            elif mode == "tech_growth":
                tech_trailing_limit = _tech_trailing_limit(row, rules)
                can_reduce = _can_reduce(row_idx, last_reduce_idx, reduce_count_since_entry, rules)
                weak_ma20 = ma_mid is not None and close < ma_mid
                volume_break = weak_ma20 and volume_ratio is not None and volume_ratio >= float(rules.get("tech_break_volume_ratio", 1.3))
                momentum_break = weak_ma20 and rsi is not None and rsi < 45
                overheat_rollover = (
                    weak_ma20
                    and peak_rsi_since_entry is not None
                    and peak_rsi_since_entry >= float(rules.get("tech_rsi_extreme", 78))
                )
                big_break = weak_ma20 and big_down_streak >= 2
                trailing_break = trailing_dd <= -tech_trailing_limit

                if ma_slow is not None and close < ma_slow and (rsi is None or rsi < 52):
                    signal = "SELL"
                    reason = "科技成长股：跌破慢线且动能转弱，趋势失效"
                elif trailing_break and (weak_ma20 or rsi is not None and rsi < 52):
                    signal = "SELL"
                    reason = "科技成长股：持仓回撤触发ATR/峰值风控"
                elif big_break:
                    signal = "SELL"
                    reason = "科技成长股：连续大阴线跌破中线，强制退出"
                elif can_reduce and (momentum_break or volume_break or overheat_rollover or trailing_break):
                    signal = "REDUCE"
                    if volume_break:
                        reason = "科技成长股：放量跌破中线，先降风险"
                    elif overheat_rollover:
                        reason = "科技成长股：极端过热后跌回中线，先降风险"
                    elif trailing_break:
                        reason = "科技成长股：触发动态回撤风控，强减仓"
                    else:
                        reason = "科技成长股：跌破中线且动能转弱，先减仓"
                elif weak_ma20 and not can_reduce:
                    reason = "科技成长股：中线转弱但已达到减仓间隔/次数限制，等待确认"
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
            elif mode == "tech_growth":
                cost_ok = True
                rsi_ok = rsi is None or (
                    rsi <= float(rules.get("tech_rsi_buy_max", 68))
                    and rsi <= float(rules.get("tech_rsi_extreme", 78))
                )
                volume_ok = volume_ratio is None or volume_ratio >= float(rules.get("tech_volume_min_ratio", 0.6))
                if not volume_ok:
                    reason = "科技成长股：趋势合格但量能极端萎缩，暂不追"
            if trend_ok and rsi_ok and cost_ok and (mode != "tech_growth" or volume_ok):
                signal = "BUY"
                reason = "趋势站稳且未明显过热" if mode != "tech_growth" else "科技成长股：站上中线且中线强于慢线，量能未极端萎缩"
            elif mode not in {"free", "tech_growth"} and cost and close <= cost * (1 - float(rules["stop_loss_pct"])):
                signal = "AVOID"
                reason = "低于参考成本且未确认止跌"

        if signal == "BUY":
            in_position = True
            entry_price = close
            peak_since_entry = close
            peak_rsi_since_entry = rsi
            last_reduce_idx = None
            reduce_count_since_entry = 0
            big_down_streak = 0
        elif signal == "REDUCE":
            last_reduce_idx = row_idx
            reduce_count_since_entry += 1
        elif signal in {"SELL", "TAKE_PROFIT"}:
            in_position = False
            entry_price = None
            peak_since_entry = None
            peak_rsi_since_entry = None
            last_reduce_idx = None
            reduce_count_since_entry = 0
            big_down_streak = 0

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


def _tech_trailing_limit(row, rules):
    atr_pct = _num(row.get("atr_pct"))
    base = float(rules.get("tech_trailing_drawdown_pct", 0.12))
    if atr_pct is None or atr_pct <= 0:
        return base
    return max(base, atr_pct * float(rules.get("tech_atr_multiplier", 2.5)))


def _can_reduce(row_idx, last_reduce_idx, reduce_count_since_entry, rules):
    max_reduce = int(_num(rules.get("tech_max_reduce_count"), 3) or 3)
    gap_days = int(_num(rules.get("tech_reduce_gap_days"), 5) or 5)
    if reduce_count_since_entry >= max_reduce:
        return False
    if last_reduce_idx is None:
        return True
    return row_idx - last_reduce_idx >= gap_days


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
                "pnl_pct": None,
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
            "exit_action_win_rate": 0,
            "trade_count": 0,
            "exit_action_count": 0,
            "round_trip_win_rate": 0,
            "round_trip_count": 0,
            "avg_round_trip_return": 0,
            "profit_factor": None,
            "avg_holding_days": 0,
            "max_single_trade_loss": 0,
            "reduce_count": 0,
            "avg_reduce_per_round_trip": 0,
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
    exit_action_win_rate = 0
    round_trip_metrics = compute_round_trip_metrics(trades)
    if trades is not None and not trades.empty:
        exits = trades[trades["action"].isin(["SELL", "TAKE_PROFIT", "REDUCE"])]
        trade_count = len(exits)
        pnl = pd.to_numeric(exits.get("pnl_pct"), errors="coerce").dropna()
        if len(pnl):
            exit_action_win_rate = (pnl > 0).mean() * 100

    result = {
        "total_return_pct": round(float(total_return * 100), 2),
        "annual_return_pct": round(float(annual_return * 100), 2),
        "sharpe": round(float(sharpe), 2),
        "max_drawdown_pct": round(float(dd.min() * 100), 2),
        "win_rate_pct": round(float(exit_action_win_rate), 2),
        "exit_action_win_rate": round(float(exit_action_win_rate), 2),
        "trade_count": int(trade_count),
        "exit_action_count": int(trade_count),
    }
    result.update(round_trip_metrics)
    return result


def compute_round_trip_metrics(trades):
    base = {
        "round_trip_win_rate": 0,
        "round_trip_count": 0,
        "avg_round_trip_return": 0,
        "profit_factor": None,
        "avg_holding_days": 0,
        "max_single_trade_loss": 0,
        "reduce_count": 0,
        "avg_reduce_per_round_trip": 0,
    }
    if trades is None or trades.empty:
        return base

    rows = trades.copy()
    rows["action"] = rows.get("action", "").astype(str)
    if "date" in rows.columns:
        rows["date"] = pd.to_datetime(rows["date"], errors="coerce")
    for col in ["price", "shares", "pnl_pct"]:
        if col in rows.columns:
            rows[col] = pd.to_numeric(rows[col], errors="coerce")

    reduce_count = int((rows["action"] == "REDUCE").sum())
    round_trips = []
    current = None
    for _, row in rows.iterrows():
        action = row.get("action")
        price = _num(row.get("price"))
        shares = _num(row.get("shares"))
        date = row.get("date")
        if action == "BUY" and price is not None and shares is not None and shares > 0:
            current = {
                "entry_date": date,
                "entry_price": price,
                "entry_shares": shares,
                "exit_value": 0.0,
                "reduce_count": 0,
            }
        elif action == "REDUCE" and current and price is not None and shares is not None and shares > 0:
            current["exit_value"] += price * shares
            current["reduce_count"] += 1
        elif action in {"SELL", "TAKE_PROFIT"} and current and price is not None and shares is not None and shares > 0:
            current["exit_value"] += price * shares
            entry_value = current["entry_price"] * current["entry_shares"]
            if entry_value > 0:
                return_pct = (current["exit_value"] / entry_value - 1) * 100
                holding_days = None
                if pd.notna(current.get("entry_date")) and pd.notna(date):
                    holding_days = max((date - current["entry_date"]).days, 0)
                round_trips.append({
                    "return_pct": return_pct,
                    "holding_days": holding_days,
                    "reduce_count": current["reduce_count"],
                })
            current = None

    count = len(round_trips)
    if count == 0:
        base["reduce_count"] = reduce_count
        return base

    returns = [item["return_pct"] for item in round_trips]
    wins = [value for value in returns if value > 0]
    losses = [value for value in returns if value < 0]
    holding_days = [item["holding_days"] for item in round_trips if item["holding_days"] is not None]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    profit_factor = None
    if gross_loss > 0:
        profit_factor = gross_profit / gross_loss

    return {
        "round_trip_win_rate": round(float(len(wins) / count * 100), 2),
        "round_trip_count": int(count),
        "avg_round_trip_return": round(float(np.mean(returns)), 2),
        "profit_factor": round(float(profit_factor), 2) if profit_factor is not None else None,
        "avg_holding_days": round(float(np.mean(holding_days)), 1) if holding_days else 0,
        "max_single_trade_loss": round(float(min(returns)), 2),
        "reduce_count": reduce_count,
        "avg_reduce_per_round_trip": round(float(np.mean([item["reduce_count"] for item in round_trips])), 2),
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
    modes = modes or BACKTEST_MODE_ORDER
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


def run_batch_strategy_mode_backtests(stock_pool, start_date, end_date, capital, provider="tushare"):
    pool = stock_pool or TECH_GROWTH_STOCK_POOL
    detail_rows = []
    failures = []
    modes = BACKTEST_MODE_ORDER

    try:
        from data_fetcher import fetch_ohlcv, infer_market_type, normalize_ticker
    except Exception as exc:
        return {
            "stock_pool": pool,
            "aggregate": pd.DataFrame(),
            "details": pd.DataFrame(),
            "failures": [{"ticker": "", "name": "", "error": f"行情模块不可用：{exc}"}],
            "summary": "批量回测失败：行情模块不可用。",
        }

    for item in pool:
        ticker = item.get("ts_code") or item.get("ticker") or item.get("code") or ""
        name = item.get("name", ticker)
        normalized = normalize_ticker(ticker)
        try:
            price_frame = fetch_ohlcv(
                normalized,
                market_type=infer_market_type(normalized),
                start=str(start_date),
                end=str(end_date),
                provider=provider,
            )
            if price_frame is None or price_frame.empty:
                failures.append({"ticker": normalized, "name": name, "error": "没有抓到可用行情"})
                continue

            multi_result = run_multi_mode_backtests(
                price_frame,
                base_rules=DEFAULT_RULES,
                cost_price=None,
                initial_cash=capital,
                modes=modes,
            )
            reports = multi_result.get("reports") or {}
            best_mode = _best_mode_by_return(reports)
            source = price_frame["source"].iloc[-1] if "source" in price_frame.columns and not price_frame.empty else provider
            data_points = int(len(price_frame))
            for mode, report in reports.items():
                metrics = report.get("metrics", {}) or {}
                total = _num(metrics.get("total_return_pct"), 0) or 0
                dd = _num(metrics.get("max_drawdown_pct"), 0) or 0
                detail_rows.append({
                    "ticker": normalized,
                    "name": name,
                    "mode": mode,
                    "mode_label": report.get("mode_label", BACKTEST_MODES.get(mode, mode)),
                    "total_return_pct": total,
                    "max_drawdown_pct": dd,
                    "exit_action_win_rate": _num(metrics.get("exit_action_win_rate"), 0) or 0,
                    "round_trip_win_rate": _num(metrics.get("round_trip_win_rate"), 0) or 0,
                    "trade_count": int(_num(metrics.get("trade_count"), 0) or 0),
                    "round_trip_count": int(_num(metrics.get("round_trip_count"), 0) or 0),
                    "avg_round_trip_return": _num(metrics.get("avg_round_trip_return"), 0) or 0,
                    "profit_factor": _num(metrics.get("profit_factor")),
                    "avg_holding_days": _num(metrics.get("avg_holding_days"), 0) or 0,
                    "max_single_trade_loss": _num(metrics.get("max_single_trade_loss"), 0) or 0,
                    "reduce_count": int(_num(metrics.get("reduce_count"), 0) or 0),
                    "avg_reduce_per_round_trip": _num(metrics.get("avg_reduce_per_round_trip"), 0) or 0,
                    "sharpe": _num(metrics.get("sharpe"), 0) or 0,
                    "calmar": _calmar_like(total, dd),
                    "positive_return": total > 0,
                    "best_return_mode": mode == best_mode,
                    "data_points": data_points,
                    "source": source,
                })
        except Exception as exc:
            failures.append({"ticker": normalized, "name": name, "error": str(exc)})

    details = pd.DataFrame(detail_rows)
    aggregate = aggregate_batch_mode_metrics(details)
    return {
        "stock_pool": pool,
        "aggregate": aggregate,
        "details": details,
        "failures": failures,
        "summary": build_batch_backtest_summary(aggregate, details, failures),
    }


def aggregate_batch_mode_metrics(details):
    if details is None or details.empty:
        return pd.DataFrame()

    rows = []
    for mode, group in details.groupby("mode", sort=False):
        mode_label = group["mode_label"].iloc[0] if "mode_label" in group.columns else BACKTEST_MODES.get(mode, mode)
        rows.append({
            "mode": mode,
            "mode_label": mode_label,
            "avg_return_pct": _round_mean(group.get("total_return_pct")),
            "median_return_pct": _round_median(group.get("total_return_pct")),
            "avg_max_drawdown_pct": _round_mean(group.get("max_drawdown_pct")),
            "median_max_drawdown_pct": _round_median(group.get("max_drawdown_pct")),
            "avg_exit_action_win_rate": _round_mean(group.get("exit_action_win_rate")),
            "avg_round_trip_win_rate": _round_mean(group.get("round_trip_win_rate")),
            "avg_trade_count": _round_mean(group.get("trade_count")),
            "avg_round_trip_count": _round_mean(group.get("round_trip_count")),
            "avg_profit_factor": _round_mean(group.get("profit_factor")),
            "avg_sharpe": _round_mean(group.get("sharpe")),
            "avg_calmar": _round_mean(group.get("calmar")),
            "positive_stock_count": int(group.get("positive_return", pd.Series(dtype=bool)).sum()),
            "tested_stock_count": int(group["ticker"].nunique()),
            "mode_win_count": int(group.get("best_return_mode", pd.Series(dtype=bool)).sum()),
            "worst_stock_return_pct": _round_min(group.get("total_return_pct")),
            "worst_stock_drawdown_pct": _round_min(group.get("max_drawdown_pct")),
            "avg_reduce_count": _round_mean(group.get("reduce_count")),
        })
    return pd.DataFrame(rows)


def build_batch_backtest_summary(aggregate, details, failures=None):
    tested = int(details["ticker"].nunique()) if details is not None and not details.empty else 0
    failed = len(failures or [])
    if aggregate is None or aggregate.empty:
        return f"科技股样本池批量回测没有形成可汇总结果；成功 {tested} 只，失败 {failed} 只。"

    best_return = aggregate.sort_values("avg_return_pct", ascending=False).iloc[0]
    best_round_trip = aggregate.sort_values("avg_round_trip_win_rate", ascending=False).iloc[0]
    best_drawdown = aggregate.sort_values("avg_max_drawdown_pct", ascending=False).iloc[0]
    free_row = aggregate[aggregate["mode"] == "free"]
    tech_row = aggregate[aggregate["mode"] == "tech_growth"]
    mode_notes = []
    if not free_row.empty:
        row = free_row.iloc[0]
        mode_notes.append(
            f"自由趋势完整交易胜率 {row['avg_round_trip_win_rate']}%，"
            f"退出动作胜率 {row['avg_exit_action_win_rate']}%，"
            f"平均收益 {row['avg_return_pct']}%，平均回撤 {row['avg_max_drawdown_pct']}%。"
        )
    if not tech_row.empty:
        row = tech_row.iloc[0]
        mode_notes.append(
            f"科技成长股完整交易胜率 {row['avg_round_trip_win_rate']}%，"
            f"退出动作胜率 {row['avg_exit_action_win_rate']}%，"
            f"平均收益 {row['avg_return_pct']}%，平均回撤 {row['avg_max_drawdown_pct']}%。"
        )

    return (
        f"批量回测成功 {tested} 只、失败 {failed} 只。"
        f"平均收益领先：{best_return['mode_label']}；"
        f"完整交易胜率领先：{best_round_trip['mode_label']}；"
        f"平均回撤控制领先：{best_drawdown['mode_label']}。"
        f"{''.join(mode_notes)}"
    )


def _best_mode_by_return(reports):
    best_mode = None
    best_return = None
    for mode, report in (reports or {}).items():
        total = _num((report.get("metrics") or {}).get("total_return_pct"))
        if total is None:
            continue
        if best_return is None or total > best_return:
            best_return = total
            best_mode = mode
    return best_mode


def _calmar_like(total_return_pct, max_drawdown_pct):
    total = _num(total_return_pct)
    dd = _num(max_drawdown_pct)
    if total is None or dd is None or dd == 0:
        return None
    return round(float(total / abs(dd)), 2)


def _clean_numeric(series):
    if series is None:
        return pd.Series(dtype=float)
    values = pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    return values


def _round_mean(series):
    values = _clean_numeric(series)
    return round(float(values.mean()), 2) if len(values) else 0


def _round_median(series):
    values = _clean_numeric(series)
    return round(float(values.median()), 2) if len(values) else 0


def _round_min(series):
    values = _clean_numeric(series)
    return round(float(values.min()), 2) if len(values) else 0


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
        return "多种模式在当前区间都没有形成可验证交易，只能参考趋势状态，不能用收益率判断优劣。"

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
        action = "暂不参与"
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
    elif mode == "tech_growth":
        next_steps.append("科技成长股模式保留趋势持有，同时用减仓间隔、减仓上限和ATR回撤线控制卖飞与回撤。")
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
