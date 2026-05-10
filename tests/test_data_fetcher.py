import unittest
import sys
import types
from unittest.mock import patch

import pandas as pd

sys.modules.setdefault(
    "yfinance",
    types.SimpleNamespace(
        Ticker=lambda *args, **kwargs: None,
        download=lambda *args, **kwargs: pd.DataFrame(),
    ),
)

from data_fetcher import compute_technical_snapshot


class DataFetcherTest(unittest.TestCase):
    def test_technical_snapshot_includes_ma120(self):
        frame = pd.DataFrame(
            {
                "Close": [10 + index * 0.1 for index in range(130)],
                "Volume": [1000] * 130,
            },
            index=pd.date_range("2026-01-01", periods=130),
        )

        with patch("data_fetcher.fetch_price_history", return_value=frame):
            snapshot = compute_technical_snapshot("002158")

        self.assertIn("ma120", snapshot)
        self.assertEqual(snapshot["ma120_state"], "站上MA120")
        self.assertNotIn("MA120", snapshot["missing"])


if __name__ == "__main__":
    unittest.main()
