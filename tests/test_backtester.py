import unittest

import pandas as pd

from backtester import DEFAULT_RULES, generate_signals, normalize_price_frame


class BacktesterTest(unittest.TestCase):
    def test_normalize_price_frame_accepts_date_index(self):
        frame = pd.DataFrame(
            {
                "Open": [10, 11],
                "High": [11, 12],
                "Low": [9, 10],
                "Close": [10.5, 11.5],
                "Volume": [1000, 1200],
            },
            index=pd.to_datetime(["2026-01-01", "2026-01-02"]),
        )
        frame.index.name = "Date"

        normalized = normalize_price_frame(frame)

        self.assertEqual(list(normalized.columns[:6]), ["date", "open", "high", "low", "close", "volume"])
        self.assertEqual(len(normalized), 2)

    def test_cost_price_blocks_chasing_more_than_three_percent_above_cost(self):
        closes = list(range(10, 80))
        frame = pd.DataFrame(
            {
                "date": pd.date_range("2026-01-01", periods=len(closes)),
                "open": closes,
                "high": [price + 1 for price in closes],
                "low": [price - 1 for price in closes],
                "close": closes,
                "volume": [1000] * len(closes),
            }
        )
        rules = {
            **DEFAULT_RULES,
            "rsi_buy_max": 100,
            "ma_fast": 3,
            "ma_mid": 5,
            "ma_slow": 10,
        }

        signals = generate_signals(frame, rules=rules, cost_price=20)

        self.assertNotIn("BUY", set(signals.tail(20)["signal"]))


if __name__ == "__main__":
    unittest.main()
