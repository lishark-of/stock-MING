import json
import tempfile
import unittest
from pathlib import Path

import trade_review_log


class TradeReviewLogTests(unittest.TestCase):
    def _sample_record(self, **overrides):
        payload = {
            "target": "688041.SS",
            "market_type": "A_SHARE_SH",
            "position_profile": {
                "shares": 500,
                "cost_price": 120,
                "margin_ratio_pct": 0,
                "analysis_horizon": "短中期",
                "api_key": "should-not-save",
            },
            "price_detail": {"price": 274.06},
            "home_snapshot": {
                "holding_action": {
                    "ticker": "688041.SH",
                    "shares": 500,
                    "cost": 120,
                    "current_price": 274.06,
                    "floating_pnl": {"amount": 77030, "pct": 128.3833},
                },
                "today_action": {
                    "overall_action": "只观察",
                    "position_mode": "持仓观察",
                    "margin_mode": "不使用融资",
                },
                "risk_breakdown": {
                    "items": [
                        {"label": "账户整体风险", "level": "低"},
                        {"label": "单票风险", "level": "中"},
                    ],
                    "token": "should-not-save",
                },
                "next_ticket_candidates": [
                    {"ticker": "601138.SS", "name": "工业富联", "action_state": "只观察", "score": 61}
                ],
                "margin_etf_summary": {
                    "watch_etfs": [
                        {"name": "半导体 ETF", "code": "512480", "status": "观察", "weight": "10%"}
                    ]
                },
                "data_freshness": {"status": "cached"},
            },
            "strategy_packet": {
                "action": "只观察",
                "add_condition": "回踩不破再评估。",
                "reduce_condition": "跌破纪律线先降风险。",
                "invalidation_condition": "趋势反向则失效。",
                "risk_budget": {"position_mode": "持仓观察"},
            },
            "projection_packet": {"paths": [{"name": "中性路径", "action": "等待"}]},
            "deepseek_summary": "",
            "user_decision": "观察",
            "user_note": "等待资金流验证。",
            "follow_up_date": "2026-06-10",
            "validation_conditions": ["资金流改善", "站稳 MA20"],
            "record_id": "fixed-id",
            "created_at": "2026-06-07T21:30:00",
        }
        payload.update(overrides)
        return trade_review_log.build_trade_review_record(**payload)

    def test_build_trade_review_record_contains_required_fields(self):
        record = self._sample_record(
            full_refresh_steps=[
                {
                    "key": "next_ticket",
                    "name": "下一票雷达",
                    "status": "empty",
                    "label": "无可执行结果",
                    "duration_seconds": 1.2,
                }
            ]
        )

        required = [
            "id",
            "created_at",
            "ticker",
            "shares",
            "cost_price",
            "current_price",
            "floating_pnl",
            "floating_pnl_pct",
            "horizon",
            "margin_ratio",
            "overall_action",
            "risk_breakdown",
            "position_budget",
            "next_ticket_top3",
            "etf_actions",
            "projection_paths",
            "strategy_conditions",
            "data_freshness",
            "deepseek_used",
            "user_decision",
        ]
        for key in required:
            self.assertIn(key, record)

        self.assertEqual(record["ticker"], "688041.SH")
        self.assertEqual(record["next_ticket_top3"][0]["ticker"], "601138.SH")
        self.assertEqual(record["user_decision"], "观察")
        self.assertFalse(record["deepseek_used"])
        self.assertEqual(record["data_freshness"]["full_refresh_steps"][0]["key"], "next_ticket")

    def test_record_does_not_include_secrets(self):
        record = self._sample_record()
        dumped = json.dumps(record, ensure_ascii=False)

        self.assertNotIn("should-not-save", dumped)
        self.assertNotIn("api_key", dumped)
        self.assertNotIn("token", dumped.lower())

    def test_append_and_load_jsonl(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trade_review_log.jsonl"
            first = self._sample_record(record_id="first", created_at="2026-06-07T10:00:00", user_decision="未执行")
            second = self._sample_record(record_id="second", created_at="2026-06-07T11:00:00", user_decision="已执行")

            trade_review_log.append_trade_review_record(first, path=path)
            trade_review_log.append_trade_review_record(second, path=path)
            loaded = trade_review_log.load_trade_review_records(limit=5, path=path)

            self.assertEqual([item["id"] for item in loaded], ["second", "first"])
            self.assertEqual(loaded[0]["user_decision"], "已执行")

    def test_missing_optional_packets_do_not_crash(self):
        record = trade_review_log.build_trade_review_record(
            target="002008.SZ",
            user_decision="放弃",
            record_id="minimal",
            created_at="2026-06-07T12:00:00",
        )

        self.assertEqual(record["ticker"], "002008.SZ")
        self.assertEqual(record["overall_action"], "等待")
        self.assertEqual(record["user_decision"], "放弃")
        self.assertEqual(record["next_ticket_top3"], [])
        self.assertFalse(record["deepseek_used"])

    def test_user_decision_is_normalized(self):
        record = self._sample_record(user_decision="奇怪输入")

        self.assertEqual(record["user_decision"], "未执行")

    def test_summarize_records_counts_latest_and_actions(self):
        records = [
            self._sample_record(record_id="latest", user_decision="观察", target="002008.SZ"),
            self._sample_record(record_id="older", user_decision="已执行", target="300750.SZ"),
        ]

        summary = trade_review_log.summarize_trade_review_records(records)

        self.assertEqual(summary["total"], 2)
        self.assertEqual(summary["latest"]["id"], "latest")
        self.assertEqual(summary["user_decisions"]["观察"], 1)

    def test_default_log_path_uses_stock_ming_cache(self):
        self.assertEqual(trade_review_log.DEFAULT_LOG_PATH.name, "trade_review_log.jsonl")
        self.assertEqual(trade_review_log.DEFAULT_LOG_PATH.parent.name, ".stock_ming_cache")


if __name__ == "__main__":
    unittest.main()
