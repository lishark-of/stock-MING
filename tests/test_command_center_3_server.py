from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from server.services import data_capability_service, evidence_service, factor_service, packet_service, position_service, quant_service, storage_service, strategy_service, task_service, trade_review_service
from server.services import migration_status_service
from server.services.task_service import clear_task_statuses_for_tests, create_task_stub, read_task_status, update_task_status


class CommandCenter3ServerServiceTests(unittest.TestCase):
    def _with_snapshot_cache(self, payload):
        original_path = packet_service.SNAPSHOT_CACHE_PATH
        temp_dir = tempfile.TemporaryDirectory()
        cache_path = Path(temp_dir.name) / "command_center_latest.json"
        cache_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        packet_service.SNAPSHOT_CACHE_PATH = cache_path
        self.addCleanup(temp_dir.cleanup)
        self.addCleanup(setattr, packet_service, "SNAPSHOT_CACHE_PATH", original_path)
        return cache_path

    def _with_meta_store(self):
        original_packet_path = packet_service.SQLITE_META_PATH
        original_factor_path = factor_service.SQLITE_META_PATH
        original_task_path = task_service.SQLITE_META_PATH
        temp_dir = tempfile.TemporaryDirectory()
        db_path = Path(temp_dir.name) / "meta.sqlite"
        packet_service.SQLITE_META_PATH = db_path
        factor_service.SQLITE_META_PATH = db_path
        task_service.SQLITE_META_PATH = db_path
        self.addCleanup(temp_dir.cleanup)
        self.addCleanup(setattr, packet_service, "SQLITE_META_PATH", original_packet_path)
        self.addCleanup(setattr, factor_service, "SQLITE_META_PATH", original_factor_path)
        self.addCleanup(setattr, task_service, "SQLITE_META_PATH", original_task_path)
        return db_path

    def _with_parquet_root(self):
        original_root = storage_service.PARQUET_ROOT
        temp_dir = tempfile.TemporaryDirectory()
        storage_service.PARQUET_ROOT = Path(temp_dir.name) / "parquet"
        self.addCleanup(temp_dir.cleanup)
        self.addCleanup(setattr, storage_service, "PARQUET_ROOT", original_root)
        return storage_service.PARQUET_ROOT

    def _with_trade_review_log(self, records):
        original_path = trade_review_service.TRADE_REVIEW_LOG_PATH
        temp_dir = tempfile.TemporaryDirectory()
        log_path = Path(temp_dir.name) / "trade_review_log.jsonl"
        with log_path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        trade_review_service.TRADE_REVIEW_LOG_PATH = log_path
        self.addCleanup(temp_dir.cleanup)
        self.addCleanup(setattr, trade_review_service, "TRADE_REVIEW_LOG_PATH", original_path)
        return log_path

    def test_cache_builders_do_not_call_external_sources(self):
        factor = packet_service.build_factor_quant_cache()
        serenity = packet_service.build_serenity_cache()
        next_session = packet_service.build_next_session_cache()
        migration = migration_status_service.build_migration_status()

        self.assertEqual(factor["packet_key"], "command_center_factor_quant_hub_packet")
        self.assertFalse(factor["deepseek_called"])
        self.assertFalse(factor["tushare_called"])
        self.assertFalse(factor["external_calls_triggered"])
        self.assertFalse(factor["governance"]["allow_core_action"])
        self.assertTrue(factor["next_session_bridge"]["does_not_modify_action"])
        self.assertTrue(factor["next_session_bridge"]["does_not_modify_operation_zones"])

        self.assertEqual(serenity["packet_key"], "command_center_serenity_method_radar_packet")
        self.assertFalse(serenity["deepseek_called"])
        self.assertTrue(serenity["decision_usage_policy"]["display_only"])

        self.assertEqual(next_session["packet_key"], "command_center_next_session_projection_packet")
        self.assertFalse(next_session["external_calls_triggered"])
        self.assertTrue(next_session["does_not_modify_action"])
        self.assertEqual(migration["packet_key"], "command_center_3_migration_status")
        self.assertEqual(len(migration["progress_baseline"]), 11)
        self.assertEqual(migration["progress_baseline"][0]["module"], "Streamlit 保留为 legacy")
        self.assertEqual(migration["progress_baseline"][-1]["current_degree"], "20%-30%")
        self.assertTrue(migration["baseline_policy"]["use_as_planning_baseline"])
        self.assertFalse(migration["api_policy"]["external_calls_triggered"])
        self.assertFalse(migration["api_policy"]["tushare_called"])
        self.assertFalse(migration["api_policy"]["deepseek_called"])
        self.assertFalse(migration["api_policy"]["github_called"])
        self.assertTrue(migration["api_policy"]["does_not_modify_strategy_action"])

        json.dumps({"factor": factor, "serenity": serenity, "next": next_session, "migration": migration}, ensure_ascii=False)

    def test_packet_service_reads_snapshot_alias_without_external_calls(self):
        self._with_snapshot_cache(
            {
                "moneyflow_packet": {
                    "status": "ready",
                    "main_net_yi": 1.25,
                }
            }
        )

        packet = packet_service.read_packet("command_center_moneyflow_packet")

        self.assertEqual(packet["packet_key"], "command_center_moneyflow_packet")
        self.assertEqual(packet["status"], "ready")
        self.assertEqual(packet["source_cache_key"], "moneyflow_packet")
        self.assertEqual(packet["cache_source"], "stock_ming_snapshot")
        self.assertFalse(packet["cache_api_external_calls_triggered"])
        self.assertFalse(packet["cache_api_tushare_called"])
        self.assertFalse(packet["cache_api_deepseek_called"])

    def test_factor_quant_cache_links_local_snapshot_context(self):
        self._with_snapshot_cache(
            {
                "a_share_fact_lineage_summary": {"items": [{"fact_key": "daily"}]},
                "strategy_packet": {"status": "ready", "action": "wait"},
                "decision_packet": {"status": "ready"},
                "quant_packet": {"status": "ready"},
            }
        )

        packet = packet_service.build_factor_quant_cache()

        self.assertEqual(packet["packet_key"], "command_center_factor_quant_hub_packet")
        self.assertEqual(packet["cache_source"], "local_builder_with_snapshot_context")
        self.assertTrue(packet["source_snapshot_available"])
        self.assertTrue(packet["linked_packets"]["a_share_fact_lineage_summary"])
        self.assertTrue(packet["linked_packets"]["strategy_execution_packet"])
        self.assertTrue(packet["linked_packets"]["decision_packet"])
        self.assertTrue(packet["linked_packets"]["legacy_quant_packet"])
        self.assertFalse(packet["external_calls_triggered"])
        self.assertFalse(packet["tushare_called"])

    def test_next_session_cache_missing_does_not_promote_legacy_projection(self):
        self._with_snapshot_cache(
            {
                "projection_packet": {
                    "base_date": "2026-06-09",
                    "historical_source_label": "当前价锚定的模拟历史段",
                    "historical": [{"t": -1, "value": 99}, {"t": 0, "value": 100}],
                    "paths": [{"name": "中性路径", "points": [{"t": 0, "value": 100}, {"t": 1, "value": 101}]}],
                    "position_context": {"current_price": 100, "cost_price": 96},
                    "reference_lines": [{"key": "current_price", "label": "当前价基准", "value": 100}],
                    "status": "ready",
                    "summary": "legacy projection exists",
                }
            }
        )

        packet = packet_service.build_next_session_cache()

        self.assertEqual(packet["packet_key"], "command_center_next_session_projection_packet")
        self.assertEqual(packet["status"], "cache_missing")
        self.assertTrue(packet["source_snapshot_available"])
        self.assertTrue(packet["legacy_projection_cache"]["available"])
        self.assertFalse(packet["external_calls_triggered"])
        self.assertTrue(packet["does_not_modify_action"])
        self.assertEqual(packet["chart_payload"]["status"], "ready")
        self.assertFalse(packet["chart_payload"]["is_exact_next_session_packet"])
        self.assertFalse(packet["chart_payload"]["uses_real_daily_close"])
        self.assertEqual(packet["chart_payload"]["historical_points"][0]["x"], "T-1")
        self.assertEqual(packet["chart_payload"]["scenario_series"][0]["scenario_name"], "中性路径")
        self.assertIn("前端不得据此计算交易动作", " ".join(packet["chart_payload"]["warnings"]))

    def test_packet_index_exposes_snapshot_keys(self):
        self._with_snapshot_cache({"moneyflow_packet": {"status": "ready"}})

        index = packet_service.list_packets()

        self.assertTrue(index["snapshot_available"])
        self.assertIn("moneyflow_packet", index["snapshot_available_keys"])
        self.assertIn("command_center_moneyflow_packet", index["snapshot_alias_keys"])
        self.assertIn("command_center_moneyflow_packet", index["available_cache_keys"])

    def test_packet_index_exposes_sqlite_packet_metadata(self):
        self._with_meta_store()
        from storage.sqlite_meta import SQLiteMetaStore

        SQLiteMetaStore(packet_service.SQLITE_META_PATH).write_packet(
            "command_center_factor_quant_hub_packet",
            {"packet_key": "command_center_factor_quant_hub_packet", "schema_version": "factor_quant_hub.v1", "mode": "light"},
        )

        index = packet_service.list_packets()

        self.assertTrue(index["sqlite_meta"]["sqlite_meta_available"])
        self.assertIn("command_center_factor_quant_hub_packet", index["persisted_packet_keys"])
        self.assertIn("command_center_factor_quant_hub_packet", index["available_cache_keys"])
        self.assertEqual(index["sqlite_meta"]["packet_metadata"][0]["schema_version"], "factor_quant_hub.v1")
        self.assertFalse(index["cache_api_policy"]["get_cache_external_calls"])

    def test_storage_factor_values_status_is_cache_only(self):
        self._with_parquet_root()

        status = storage_service.factor_values_status()

        self.assertEqual(status["dataset"], "factor_values")
        self.assertTrue(status["cache_only"])
        self.assertFalse(status["external_calls_triggered"])
        self.assertFalse(status["tushare_called"])
        self.assertFalse(status["deepseek_called"])
        self.assertTrue(status["does_not_execute_trades"])
        self.assertIn(status["metadata"]["status"], {"missing", "ready"})

    def test_storage_overview_covers_daily_moneyflow_and_factor_values(self):
        self._with_parquet_root()

        overview = storage_service.storage_overview()

        self.assertEqual(overview["store"], "parquet_duckdb")
        self.assertEqual(set(overview["dataset_status"]), {"factor_values", "daily", "moneyflow"})
        self.assertTrue(overview["cache_only"])
        self.assertFalse(overview["external_calls_triggered"])
        self.assertFalse(overview["tushare_called"])
        self.assertTrue(overview["does_not_execute_trades"])

    def test_storage_dataset_rejects_unsupported_names_without_external_calls(self):
        self._with_parquet_root()

        status = storage_service.parquet_dataset_status("../secret")

        self.assertEqual(status["status"], "unsupported_dataset")
        self.assertEqual(set(status["supported_datasets"]), {"factor_values", "daily", "moneyflow"})
        self.assertFalse(status["external_calls_triggered"])
        self.assertFalse(status["tushare_called"])

    def test_trade_review_cache_reads_local_log_without_external_calls(self):
        self._with_trade_review_log(
            [
                {
                    "id": "r1",
                    "created_at": "2026-06-10T09:30:00",
                    "ticker": "002008.SZ",
                    "user_decision": "观察",
                    "overall_action": "等待",
                    "strategy_action": "wait",
                    "user_note": "复盘纪律",
                    "api_key": "SHOULD_DROP",
                    "deepseek_summary": "Traceback token=SHOULD_DROP",
                }
            ]
        )

        packet = trade_review_service.read_trade_review_cache()

        self.assertEqual(packet["packet_key"], "command_center_3_trade_review_cache")
        self.assertEqual(packet["status"], "ready")
        self.assertTrue(packet["cache_only"])
        self.assertTrue(packet["read_only"])
        self.assertEqual(packet["record_count"], 1)
        self.assertEqual(packet["records"][0]["ticker"], "002008.SZ")
        self.assertNotIn("api_key", packet["records"][0])
        self.assertNotIn("SHOULD_DROP", json.dumps(packet, ensure_ascii=False))
        self.assertEqual(packet["call_ledger"][0]["api"], "local_trade_review_log")
        self.assertEqual(packet["call_ledger"][0]["call_status"], "cache_read")
        self.assertFalse(packet["external_calls_triggered"])
        self.assertFalse(packet["tushare_called"])
        self.assertFalse(packet["deepseek_called"])
        self.assertFalse(packet["github_called"])
        self.assertTrue(packet["does_not_execute_trades"])
        self.assertTrue(packet["does_not_modify_strategy_action"])
        self.assertTrue(packet["does_not_write_cache"])
        self.assertFalse(packet["contains_secret"])
        json.dumps(packet, ensure_ascii=False)

    def test_quant_cache_reads_local_quant_packet_without_running_backtest(self):
        self._with_snapshot_cache(
            {
                "quant_packet": {
                    "status": "ready",
                    "score": 68,
                    "confidence": "中",
                    "action_state": "轻仓验证",
                    "data_status": "ready",
                    "summary": "量化缓存可参考",
                    "evidence_items": ["量化分数：68"],
                    "risk_notes": ["回测收益不代表未来收益"],
                    "decision_brief": {"status": "ready", "headline": "量化可进入证据链"},
                    "api_key": "SHOULD_DROP",
                }
            }
        )

        packet = quant_service.read_quant_backtest_cache()

        self.assertEqual(packet["packet_key"], "command_center_3_quant_backtest_cache")
        self.assertEqual(packet["status"], "ready")
        self.assertEqual(packet["mode"], "cache_only")
        self.assertEqual(packet["source_packet_key"], "command_center_quant_packet")
        self.assertEqual(packet["quant_packet"]["score"], 68)
        self.assertNotIn("api_key", packet["quant_packet"])
        self.assertNotIn("SHOULD_DROP", json.dumps(packet, ensure_ascii=False))
        self.assertTrue(packet["policy"]["does_not_run_backtest"])
        self.assertFalse(packet["external_calls_triggered"])
        self.assertFalse(packet["tushare_called"])
        self.assertFalse(packet["deepseek_called"])
        self.assertFalse(packet["github_called"])
        self.assertTrue(packet["does_not_execute_trades"])
        self.assertTrue(packet["does_not_modify_strategy_action"])
        self.assertEqual(packet["call_ledger"][0]["api"], "local_quant_backtest_cache")
        json.dumps(packet, ensure_ascii=False)

    def test_strategy_trace_cache_reads_strategy_and_decision_without_mutating_action(self):
        self._with_snapshot_cache(
            {
                "strategy_packet": {
                    "status": "ready",
                    "action": "等待",
                    "confidence": "中",
                    "position_advice": "只观察，不追高。",
                    "summary": "结构化规则给出等待。",
                    "strategy_execution_trace": {
                        "input_sources": [{"name": "量化推演", "status": "ready", "used": True, "summary": "缓存可用"}],
                        "rules_fired": [{"rule": "验证不足", "result": "等待", "evidence": "待确认", "impact": "不加仓"}],
                        "missing_inputs": ["交易纪律/回测"],
                        "final_reason": "结构化规则给出等待。",
                        "deepseek_used": False,
                    },
                    "api_key": "SHOULD_DROP",
                },
                "decision_packet": {
                    "status": "ready",
                    "overall_action": "只观察",
                    "market_bias": "中性",
                    "authorization": "Bearer SHOULD_DROP",
                },
            }
        )

        packet = strategy_service.read_strategy_trace_cache()

        self.assertEqual(packet["packet_key"], "command_center_3_strategy_trace_cache")
        self.assertEqual(packet["status"], "ready")
        self.assertEqual(packet["mode"], "cache_only")
        self.assertTrue(packet["cache_only"])
        self.assertEqual(packet["action_summary"]["action"], "等待")
        self.assertEqual(packet["action_summary"]["action_source"], "strategy_execution_packet")
        self.assertEqual(packet["decision_summary"]["overall_action"], "只观察")
        self.assertEqual(packet["strategy_trace"]["rules_fired"][0]["rule"], "验证不足")
        self.assertNotIn("api_key", packet["strategy_packet"])
        self.assertNotIn("authorization", packet["decision_packet"])
        self.assertNotIn("SHOULD_DROP", json.dumps(packet, ensure_ascii=False))
        self.assertTrue(packet["policy"]["does_not_call_tushare"])
        self.assertTrue(packet["policy"]["does_not_call_deepseek"])
        self.assertTrue(packet["policy"]["does_not_run_backtest"])
        self.assertFalse(packet["external_calls_triggered"])
        self.assertFalse(packet["tushare_called"])
        self.assertFalse(packet["deepseek_called"])
        self.assertFalse(packet["github_called"])
        self.assertTrue(packet["does_not_execute_trades"])
        self.assertTrue(packet["does_not_modify_strategy_action"])
        self.assertTrue(packet["does_not_modify_decision_packet"])
        self.assertEqual(packet["call_ledger"][0]["api"], "local_strategy_trace_cache")
        json.dumps(packet, ensure_ascii=False)

    def test_position_context_cache_reads_home_snapshot_without_external_calls(self):
        self._with_snapshot_cache(
            {
                "holding_action": {
                    "ticker": "002008.SZ",
                    "name": "大族激光",
                    "shares": 3000,
                    "cost": 108,
                    "current_price": 112,
                    "floating_pnl_text": "浮盈",
                    "action_state": "只观察",
                    "api_key": "SHOULD_DROP",
                },
                "position_risk_budget": {"risk_level": "中", "max_add_amount": 0},
                "risk_breakdown": {"position": "cache"},
                "safety_line": {"stop_loss": 100},
                "today_action": {"overall_action": "只观察"},
                "strategy_packet": {"action": "等待", "confidence": "中", "authorization": "Bearer SHOULD_DROP"},
            }
        )

        packet = position_service.read_position_context_cache()

        self.assertEqual(packet["packet_key"], "command_center_3_position_context_cache")
        self.assertEqual(packet["status"], "ready")
        self.assertEqual(packet["mode"], "cache_only")
        self.assertTrue(packet["cache_only"])
        self.assertEqual(packet["position_summary"]["ticker"], "002008.SZ")
        self.assertEqual(packet["holding_action"]["shares"], 3000)
        self.assertEqual(packet["today_action"]["overall_action"], "只观察")
        self.assertEqual(packet["strategy_context"]["action"], "等待")
        self.assertNotIn("api_key", packet["holding_action"])
        self.assertNotIn("authorization", packet["strategy_context"])
        self.assertNotIn("SHOULD_DROP", json.dumps(packet, ensure_ascii=False))
        self.assertTrue(packet["policy"]["does_not_call_tushare"])
        self.assertTrue(packet["policy"]["does_not_call_deepseek"])
        self.assertTrue(packet["policy"]["does_not_recalculate_position"])
        self.assertFalse(packet["external_calls_triggered"])
        self.assertFalse(packet["tushare_called"])
        self.assertFalse(packet["deepseek_called"])
        self.assertFalse(packet["github_called"])
        self.assertTrue(packet["does_not_execute_trades"])
        self.assertTrue(packet["does_not_modify_strategy_action"])
        self.assertTrue(packet["does_not_modify_holdings"])
        self.assertEqual(packet["call_ledger"][0]["api"], "local_position_context_cache")
        json.dumps(packet, ensure_ascii=False)

    def test_a_share_evidence_cache_builds_lineage_without_external_calls(self):
        self._with_snapshot_cache(
            {
                "moneyflow_packet": {
                    "status": "ready",
                    "trade_date": "20260610",
                    "updated_at": "2026-06-10T09:30:00",
                    "flow_state": "主力净流入",
                    "main_net_yi": 1.2,
                    "api_key": "SHOULD_DROP",
                },
                "a_share_fact_lineage_summary": {
                    "schema_version": "a_share_fact_lineage_summary.v1",
                    "summary": "已验证 1｜阻断 0｜缓存 0｜过期 0｜缺失 0｜待验证 0",
                    "items": [{"fact_key": "moneyflow", "status_label": "已验证", "enters_core_action": False}],
                    "counts": {"verified": 1, "blocked": 0, "missing": 0, "cached": 0},
                },
            }
        )

        packet = evidence_service.read_a_share_evidence_cache()

        self.assertEqual(packet["packet_key"], "command_center_3_a_share_evidence_cache")
        self.assertEqual(packet["status"], "ready")
        self.assertTrue(packet["cache_only"])
        self.assertEqual(packet["mode"], "cache_only")
        self.assertEqual(packet["fact_lineage"]["schema_version"], "a_share_fact_lineage_summary.v1")
        self.assertEqual(packet["counts"]["lineage_verified"], 1)
        self.assertNotIn("SHOULD_DROP", json.dumps(packet, ensure_ascii=False))
        self.assertTrue(packet["policy"]["does_not_call_tushare"])
        self.assertFalse(packet["policy"]["lineage_enters_core_action"])
        self.assertFalse(packet["external_calls_triggered"])
        self.assertFalse(packet["tushare_called"])
        self.assertFalse(packet["deepseek_called"])
        self.assertFalse(packet["github_called"])
        self.assertTrue(packet["does_not_execute_trades"])
        self.assertTrue(packet["does_not_modify_strategy_action"])
        self.assertEqual(packet["call_ledger"][0]["api"], "local_a_share_evidence_cache")
        json.dumps(packet, ensure_ascii=False)

    def test_data_capability_cache_reads_local_capability_without_provider_ping(self):
        self._with_snapshot_cache(
            {
                "data_capability": {
                    "source": "Unified data capability",
                    "items": [
                        {
                            "provider": "Tushare",
                            "api": "moneyflow",
                            "label": "个股资金流",
                            "capability_state": "available",
                            "status": "可用",
                            "latest_date": "20260610",
                            "api_key": "SHOULD_DROP",
                        },
                        {
                            "provider": "Supabase",
                            "api": "brain_memory",
                            "label": "brain_memory",
                            "capability_state": "not_configured",
                            "status": "未配置",
                        },
                    ],
                }
            }
        )

        packet = data_capability_service.read_data_capability_cache()

        self.assertEqual(packet["packet_key"], "command_center_3_data_capability_cache")
        self.assertEqual(packet["mode"], "cache_only")
        self.assertTrue(packet["cache_only"])
        self.assertGreaterEqual(packet["counts"]["available"], 1)
        self.assertGreaterEqual(packet["counts"]["restricted"], 1)
        self.assertNotIn("SHOULD_DROP", json.dumps(packet, ensure_ascii=False))
        self.assertTrue(packet["policy"]["does_not_ping_tushare"])
        self.assertTrue(packet["policy"]["does_not_ping_supabase"])
        self.assertFalse(packet["external_calls_triggered"])
        self.assertFalse(packet["tushare_called"])
        self.assertFalse(packet["deepseek_called"])
        self.assertFalse(packet["github_called"])
        self.assertTrue(packet["does_not_execute_trades"])
        self.assertTrue(packet["does_not_modify_strategy_action"])
        self.assertEqual(packet["call_ledger"][0]["api"], "local_data_capability_cache")
        json.dumps(packet, ensure_ascii=False)

    def test_factor_value_rows_keep_safe_scalar_contract(self):
        rows = storage_service._factor_value_rows_from_hub(
            {
                "packet_key": "command_center_factor_quant_hub_packet",
                "mode": "light",
                "cache_source": "local_factor_light_pipeline",
                "runtime": {
                    "trade_date": "20260610",
                    "calculated_at": "2026-06-10T09:30:00",
                    "factor_values": [
                        {
                            "factor_key": "momentum_20d",
                            "factor_name": "20日动量",
                            "raw_value": {"not": "scalar"},
                            "zscore": [1, 2],
                            "rank_pct": 0.7,
                            "direction": "support",
                            "data_status": "ready",
                            "status_note": "Traceback token=SHOULD_DROP",
                            "pit_validated": True,
                        }
                    ],
                },
                "universe": {"items": ["002008.SZ"]},
            }
        )

        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["ts_code"], "002008.SZ")
        self.assertEqual(row["trade_date"], "20260610")
        self.assertEqual(row["factor_key"], "momentum_20d")
        self.assertEqual(row["data_status"], "ready")
        self.assertEqual(row["rank_pct"], 0.7)
        self.assertIsNone(row["raw_value"])
        self.assertIsNone(row["zscore"])
        self.assertIsNone(row["status_note"])
        self.assertEqual(row["packet_key"], "command_center_factor_quant_hub_packet")
        self.assertEqual(row["source_packet"], "runtime.factor_values")
        self.assertEqual(row["source"], "local_factor_light_pipeline")
        self.assertNotIn("SHOULD_DROP", json.dumps(row, ensure_ascii=False))

    def test_persist_factor_values_failed_write_returns_safe_status(self):
        self._with_parquet_root()
        original_dependency_status = storage_service.parquet_store.dependency_status
        original_write_dataset = storage_service.parquet_store.write_dataset

        storage_service.parquet_store.dependency_status = lambda: {"available": True, "error_message_safe": ""}

        def fail_write(*args, **kwargs):
            raise RuntimeError('Traceback File "x.py" token=SHOULD_DROP')

        storage_service.parquet_store.write_dataset = fail_write
        self.addCleanup(setattr, storage_service.parquet_store, "dependency_status", original_dependency_status)
        self.addCleanup(setattr, storage_service.parquet_store, "write_dataset", original_write_dataset)

        result = storage_service.persist_factor_values_from_hub(
            {
                "runtime": {
                    "factor_values": [
                        {"factor_key": "momentum_20d", "raw_value": 1.2, "data_status": "ready"},
                    ]
                },
                "universe": {"items": ["002008.SZ"]},
            }
        )

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["dataset"], "factor_values")
        self.assertEqual(result["row_count"], 0)
        self.assertEqual(result["error_message_safe"], "local parquet factor_values write failed")
        self.assertFalse(result["external_calls_triggered"])
        self.assertTrue(result["does_not_modify_strategy_action"])
        self.assertNotIn("SHOULD_DROP", json.dumps(result, ensure_ascii=False))

    def test_task_stub_records_safe_status_without_external_work(self):
        self._with_meta_store()
        clear_task_statuses_for_tests(clear_persisted=True)
        task = create_task_stub(
            "refresh_factor_data",
            payload={"ts_code": "002008.SZ", "token": "SHOULD_NOT_KEEP", "nested": {"api_key": "DROP", "keep": "ok"}},
        )

        self.assertTrue(task["task_id"].startswith("local-"))
        self.assertEqual(task["status"], "success")
        self.assertEqual(task["progress"], 1.0)
        self.assertEqual(task["current_step"], "stub_created_no_external_call")
        self.assertEqual([item["status"] for item in task["status_history"]], ["pending", "running", "success"])
        self.assertEqual(task["call_ledger"][0]["call_status"], "stub_not_called")
        self.assertEqual(task["backend"], "local_fallback")
        self.assertNotIn("token", task["payload_safe"])
        self.assertEqual(task["payload_safe"]["nested"], {"keep": "ok"})
        self.assertFalse(task["external_calls_triggered"])
        self.assertFalse(task["tushare_called"])
        self.assertTrue(task["does_not_execute_trades"])
        self.assertEqual(read_task_status(task["task_id"])["task_id"], task["task_id"])
        task_service._TASKS.clear()
        persisted = read_task_status(task["task_id"])
        self.assertIsNotNone(persisted)
        self.assertEqual(persisted["task_id"], task["task_id"])
        self.assertEqual(task_service.list_task_statuses()[0]["task_id"], task["task_id"])

    def test_task_catalog_documents_button_gated_external_boundaries(self):
        catalog = task_service.build_task_catalog()

        self.assertEqual(catalog["packet_key"], "command_center_3_task_catalog")
        self.assertEqual(catalog["task_count"], 6)
        self.assertTrue(catalog["policy"]["get_catalog_cache_only"])
        self.assertTrue(catalog["policy"]["all_tasks_button_gated"])
        self.assertTrue(catalog["policy"]["call_ledger_required_for_all"])
        self.assertFalse(catalog["external_calls_triggered"])
        self.assertFalse(catalog["tushare_called"])
        self.assertFalse(catalog["deepseek_called"])
        self.assertFalse(catalog["github_called"])
        self.assertTrue(catalog["policy"]["does_not_execute_trades"])
        self.assertTrue(catalog["policy"]["does_not_modify_strategy_action"])
        self.assertEqual(set(catalog["external_sources"]), {"deepseek", "github", "tushare"})
        by_type = {item["task_type"]: item for item in catalog["tasks"]}
        self.assertEqual(by_type["refresh_factor_data"]["route"], "POST /api/factor-quant/refresh-data")
        self.assertIn("tushare", by_type["refresh_factor_data"]["possible_external_sources"])
        self.assertIn("deepseek", by_type["run_deepseek_factor_explanation"]["possible_external_sources"])
        self.assertIn("github", by_type["probe_serenity_github"]["possible_external_sources"])
        self.assertEqual(by_type["run_factor_light"]["possible_external_sources"], [])

    def test_task_status_update_supports_failed_state_without_secret_leak(self):
        self._with_meta_store()
        task = create_task_stub("run_factor_light", payload={"authorization": "Bearer secret", "ts_code": "002008.SZ"})

        updated = update_task_status(
            task["task_id"],
            status="failed",
            progress=0.7,
            current_step="safe_failure_recorded",
            error_message_safe="mock failure",
            warning="safe warning",
        )

        self.assertIsNotNone(updated)
        self.assertEqual(updated["status"], "failed")
        self.assertEqual(updated["current_step"], "safe_failure_recorded")
        self.assertEqual(updated["error_message_safe"], "mock failure")
        self.assertNotIn("authorization", updated["payload_safe"])
        self.assertIn("safe warning", updated["warnings"])

    def test_factor_run_light_writes_local_cache_without_external_calls(self):
        self._with_snapshot_cache(
            {
                "timestamp": "2026-06-10T09:30:00",
                "moneyflow_packet": {"status": "ready", "ticker": "002008.SZ", "main_net_yi": 1.2, "small_net_yi": -0.4},
                "hard_risk_packet": {"status": "ready", "risk_flags": []},
                "limit_emotion_packet": {"status": "ready", "limit_heat_score": 1},
                "chip_packet": {"status": "ready", "winner_rate": 40},
                "strategy_packet": {"status": "ready", "action": "wait"},
                "decision_packet": {"status": "ready"},
                "quant_packet": {"status": "ready"},
                "a_share_fact_lineage_summary": {"items": [{"fact_key": "moneyflow"}]},
            }
        )
        self._with_meta_store()
        self._with_parquet_root()

        task = factor_service.create_factor_task(
            "run_factor_light",
            payload={"ts_code": "002008.SZ", "api_key": "SHOULD_DROP"},
        )
        packet = packet_service.build_factor_quant_cache()

        self.assertEqual(task["status"], "success")
        self.assertEqual(task["current_step"], "factor_light_completed_from_local_cache")
        self.assertEqual(task["call_ledger"][0]["call_status"], "cache_read")
        storage_ledger = [item for item in task["call_ledger"] if item.get("api") == "local_parquet_factor_values"]
        self.assertEqual(len(storage_ledger), 1)
        self.assertIn(storage_ledger[0]["call_status"], {"written", "dependency_missing", "empty"})
        self.assertNotIn("api_key", task["payload_safe"])
        self.assertFalse(task["external_calls_triggered"])

        self.assertEqual(packet["packet_key"], "command_center_factor_quant_hub_packet")
        self.assertEqual(packet["mode"], "light")
        self.assertEqual(packet["cache_source"], "sqlite_meta")
        self.assertFalse(packet["tushare_called"])
        self.assertFalse(packet["deepseek_called"])
        self.assertFalse(packet["external_calls_triggered"])
        self.assertEqual(packet["factor_values_storage"]["dataset"], "factor_values")
        self.assertIn(packet["factor_values_storage"]["status"], {"written", "dependency_missing", "empty"})
        self.assertIn("local_parquet_factor_values", {item.get("api") for item in packet["storage_call_ledger"]})
        self.assertFalse(packet["governance"]["allow_core_action"])
        self.assertTrue(packet["next_session_bridge"]["does_not_modify_action"])
        support_keys = {item.get("factor_key") for item in packet["score"]["support_factors"]}
        suppress_keys = {item.get("factor_key") for item in packet["score"]["suppress_factors"]}
        self.assertNotIn("serenity_method_source", support_keys | suppress_keys)
        self.assertNotIn("chokepoint_method_hint", support_keys | suppress_keys)
        self.assertIn("roe_latest", {item.get("factor_key") for item in packet["score"]["missing_factors"]})

    def test_deepseek_explanation_task_prepares_prompt_without_model_call(self):
        self._with_meta_store()

        task = factor_service.create_factor_task("run_deepseek_factor_explanation", payload={"ts_code": "002008.SZ"})
        packet = packet_service.build_factor_quant_cache()

        self.assertEqual(task["status"], "success")
        self.assertEqual(task["current_step"], "deepseek_prompt_ready_without_model_call")
        self.assertEqual(task["call_ledger"][0]["call_status"], "not_called")
        self.assertFalse(task["deepseek_called"])
        self.assertFalse(task["external_calls_triggered"])
        self.assertTrue(task["does_not_execute_trades"])

        self.assertEqual(packet["cache_source"], "sqlite_meta")
        self.assertFalse(packet["deepseek_called"])
        self.assertFalse(packet["deepseek_model_called"])
        self.assertFalse(packet["deepseek_task_external_calls_triggered"])
        self.assertEqual(packet["deepseek_explanation"]["status"], "not_called")
        self.assertEqual(packet["deepseek_explanation"]["payload"], None)
        self.assertFalse(packet["deepseek_explanation_prompt_preview"]["enters_deepseek_prompt"])
        self.assertTrue(packet["deepseek_explanation_prompt_preview"]["would_enter_deepseek_prompt_if_user_authorizes"])
        self.assertFalse(packet["governance"]["allow_core_action"])
        self.assertTrue(packet["next_session_bridge"]["does_not_modify_action"])

    def test_deepseek_explanation_task_sanitizes_payload_without_overwriting_values(self):
        self._with_meta_store()
        forbidden = {
            "summary": "只解释已有结构化结果",
            "support_notes": ["量能支持"],
            "strategy_action": "buy",
            "action": "买入",
            "price": 99,
            "position": {"shares": 1000},
            "factor_values": [{"raw_value": 1.2}],
            "packet": {"full": True},
        }

        task = factor_service.create_factor_task(
            "run_deepseek_factor_explanation",
            payload={"provided_explanation": forbidden, "api_key": "DROP"},
        )
        packet = packet_service.build_factor_quant_cache()
        explanation = packet["deepseek_explanation"]

        self.assertEqual(task["status"], "success")
        self.assertEqual(task["current_step"], "deepseek_explanation_sanitized_without_model_call")
        self.assertEqual(task["call_ledger"][0]["call_status"], "provided_payload_sanitized")
        self.assertEqual(task["payload_safe"], {"provided_explanation_payload": True})
        self.assertNotIn("api_key", task["payload_safe"])
        self.assertNotIn("provided_explanation", task["payload_safe"])
        self.assertNotIn("price", json.dumps(task["payload_safe"], ensure_ascii=False))
        self.assertFalse(task["deepseek_called"])
        self.assertFalse(task["external_calls_triggered"])

        self.assertFalse(packet["deepseek_called"])
        self.assertFalse(packet["deepseek_model_called"])
        self.assertEqual(explanation["status"], "success")
        self.assertEqual(explanation["payload"]["summary"], "只解释已有结构化结果")
        self.assertEqual(set(explanation["payload"]), {
            "summary",
            "support_notes",
            "suppress_notes",
            "conflict_notes",
            "missing_data_notes",
            "discipline_notes",
        })
        for forbidden_key in ("strategy_action", "action", "price", "position", "factor_values", "packet"):
            self.assertIn(forbidden_key, explanation["ignored_keys"])
            self.assertNotIn(forbidden_key, explanation["payload"])
        self.assertTrue(explanation["does_not_override_numeric_values"])
        self.assertFalse(packet["governance"]["allow_core_action"])
        self.assertTrue(packet["next_session_bridge"]["does_not_modify_operation_zones"])


@unittest.skipIf(importlib.util.find_spec("fastapi") is None, "FastAPI is not installed in this environment")
class CommandCenter3FastAPITests(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient
        from server.main import app

        self.client = TestClient(app)

    def _with_snapshot_cache(self, payload):
        original_path = packet_service.SNAPSHOT_CACHE_PATH
        temp_dir = tempfile.TemporaryDirectory()
        cache_path = Path(temp_dir.name) / "command_center_latest.json"
        cache_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        packet_service.SNAPSHOT_CACHE_PATH = cache_path
        self.addCleanup(temp_dir.cleanup)
        self.addCleanup(setattr, packet_service, "SNAPSHOT_CACHE_PATH", original_path)
        return cache_path

    def _with_meta_store(self):
        original_packet_path = packet_service.SQLITE_META_PATH
        original_factor_path = factor_service.SQLITE_META_PATH
        original_task_path = task_service.SQLITE_META_PATH
        temp_dir = tempfile.TemporaryDirectory()
        db_path = Path(temp_dir.name) / "meta.sqlite"
        packet_service.SQLITE_META_PATH = db_path
        factor_service.SQLITE_META_PATH = db_path
        task_service.SQLITE_META_PATH = db_path
        self.addCleanup(temp_dir.cleanup)
        self.addCleanup(setattr, packet_service, "SQLITE_META_PATH", original_packet_path)
        self.addCleanup(setattr, factor_service, "SQLITE_META_PATH", original_factor_path)
        self.addCleanup(setattr, task_service, "SQLITE_META_PATH", original_task_path)
        return db_path

    def _with_parquet_root(self):
        original_root = storage_service.PARQUET_ROOT
        temp_dir = tempfile.TemporaryDirectory()
        storage_service.PARQUET_ROOT = Path(temp_dir.name) / "parquet"
        self.addCleanup(temp_dir.cleanup)
        self.addCleanup(setattr, storage_service, "PARQUET_ROOT", original_root)
        return storage_service.PARQUET_ROOT

    def _with_trade_review_log(self, records):
        original_path = trade_review_service.TRADE_REVIEW_LOG_PATH
        temp_dir = tempfile.TemporaryDirectory()
        log_path = Path(temp_dir.name) / "trade_review_log.jsonl"
        with log_path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        trade_review_service.TRADE_REVIEW_LOG_PATH = log_path
        self.addCleanup(temp_dir.cleanup)
        self.addCleanup(setattr, trade_review_service, "TRADE_REVIEW_LOG_PATH", original_path)
        return log_path

    def test_health_and_cache_endpoints(self):
        health = self.client.get("/health").json()
        self.assertTrue(health["ok"])
        self.assertFalse(health["data"]["external_calls_on_startup"])
        self.assertFalse(health["data"]["deepseek_called"])
        self.assertFalse(health["data"]["tushare_called"])
        model_strategy = health["data"]["deepseek_model_strategy"]
        self.assertTrue(model_strategy["explain"])
        self.assertTrue(model_strategy["fast"])
        self.assertTrue(model_strategy["default"])
        self.assertFalse(model_strategy["contains_secret"])
        self.assertNotIn("token", json.dumps(model_strategy, ensure_ascii=False).lower())
        self.assertNotIn("api_key", json.dumps(model_strategy, ensure_ascii=False).lower())

        factor = self.client.get("/api/factor-quant/cache").json()
        self.assertTrue(factor["ok"])
        self.assertEqual(factor["data"]["mode"], "cache_only")
        self.assertFalse(factor["data"]["external_calls_triggered"])

        serenity = self.client.get("/api/serenity/cache").json()
        self.assertTrue(serenity["ok"])
        self.assertFalse(serenity["data"]["deepseek_called"])

        next_session = self.client.get("/api/next-session/cache").json()
        self.assertTrue(next_session["ok"])
        self.assertFalse(next_session["data"]["external_calls_triggered"])

        storage = self.client.get("/api/storage/factor-values").json()
        self.assertTrue(storage["ok"])
        self.assertTrue(storage["data"]["cache_only"])
        self.assertFalse(storage["data"]["external_calls_triggered"])

        storage_overview = self.client.get("/api/storage").json()
        self.assertTrue(storage_overview["ok"])
        self.assertEqual(set(storage_overview["data"]["dataset_status"]), {"factor_values", "daily", "moneyflow"})
        self.assertFalse(storage_overview["data"]["external_calls_triggered"])

        daily_storage = self.client.get("/api/storage/daily").json()
        self.assertTrue(daily_storage["ok"])
        self.assertEqual(daily_storage["data"]["dataset"], "daily")
        self.assertFalse(daily_storage["data"]["external_calls_triggered"])

        migration = self.client.get("/api/migration/status").json()
        self.assertTrue(migration["ok"])
        self.assertEqual(migration["data"]["status"], "active_migration")
        self.assertEqual(len(migration["data"]["progress_baseline"]), 11)
        self.assertTrue(migration["data"]["baseline_policy"]["do_not_reestimate_every_turn"])
        self.assertTrue(migration["data"]["api_policy"]["cache_only"])
        self.assertFalse(migration["data"]["api_policy"]["external_calls_triggered"])
        self.assertTrue(migration["data"]["api_policy"]["does_not_execute_trades"])

        task_catalog = self.client.get("/api/tasks/catalog").json()
        self.assertTrue(task_catalog["ok"])
        self.assertEqual(task_catalog["data"]["task_count"], 6)
        self.assertTrue(task_catalog["data"]["policy"]["get_catalog_cache_only"])
        self.assertTrue(task_catalog["data"]["policy"]["all_tasks_button_gated"])
        self.assertTrue(task_catalog["data"]["policy"]["call_ledger_required_for_all"])
        self.assertFalse(task_catalog["data"]["external_calls_triggered"])
        self.assertFalse(task_catalog["data"]["tushare_called"])
        self.assertFalse(task_catalog["data"]["deepseek_called"])
        self.assertFalse(task_catalog["data"]["github_called"])

        trade_review = self.client.get("/api/trade-review/cache").json()
        self.assertTrue(trade_review["ok"])
        self.assertTrue(trade_review["data"]["cache_only"])
        self.assertFalse(trade_review["data"]["external_calls_triggered"])
        self.assertFalse(trade_review["data"]["tushare_called"])
        self.assertFalse(trade_review["data"]["deepseek_called"])
        self.assertTrue(trade_review["data"]["does_not_execute_trades"])

        quant = self.client.get("/api/quant/cache").json()
        self.assertTrue(quant["ok"])
        self.assertTrue(quant["data"]["cache_only"])
        self.assertTrue(quant["data"]["policy"]["does_not_run_backtest"])
        self.assertFalse(quant["data"]["external_calls_triggered"])
        self.assertFalse(quant["data"]["tushare_called"])
        self.assertFalse(quant["data"]["deepseek_called"])
        self.assertTrue(quant["data"]["does_not_modify_strategy_action"])

        strategy = self.client.get("/api/strategy/cache").json()
        self.assertTrue(strategy["ok"])
        self.assertTrue(strategy["data"]["cache_only"])
        self.assertFalse(strategy["data"]["external_calls_triggered"])
        self.assertFalse(strategy["data"]["tushare_called"])
        self.assertFalse(strategy["data"]["deepseek_called"])
        self.assertTrue(strategy["data"]["policy"]["does_not_run_backtest"])
        self.assertTrue(strategy["data"]["does_not_modify_strategy_action"])
        self.assertTrue(strategy["data"]["does_not_execute_trades"])

        position = self.client.get("/api/position/cache").json()
        self.assertTrue(position["ok"])
        self.assertTrue(position["data"]["cache_only"])
        self.assertFalse(position["data"]["external_calls_triggered"])
        self.assertFalse(position["data"]["tushare_called"])
        self.assertFalse(position["data"]["deepseek_called"])
        self.assertTrue(position["data"]["policy"]["does_not_recalculate_position"])
        self.assertTrue(position["data"]["does_not_modify_strategy_action"])
        self.assertTrue(position["data"]["does_not_modify_holdings"])
        self.assertTrue(position["data"]["does_not_execute_trades"])

        evidence = self.client.get("/api/evidence/cache").json()
        self.assertTrue(evidence["ok"])
        self.assertTrue(evidence["data"]["cache_only"])
        self.assertFalse(evidence["data"]["external_calls_triggered"])
        self.assertFalse(evidence["data"]["tushare_called"])
        self.assertFalse(evidence["data"]["deepseek_called"])
        self.assertTrue(evidence["data"]["does_not_modify_strategy_action"])

        data_capability = self.client.get("/api/data-capability/cache").json()
        self.assertTrue(data_capability["ok"])
        self.assertTrue(data_capability["data"]["cache_only"])
        self.assertFalse(data_capability["data"]["external_calls_triggered"])
        self.assertFalse(data_capability["data"]["tushare_called"])
        self.assertFalse(data_capability["data"]["deepseek_called"])
        self.assertTrue(data_capability["data"]["policy"]["does_not_ping_tushare"])
        self.assertTrue(data_capability["data"]["does_not_modify_strategy_action"])

    def test_trade_review_cache_endpoint_returns_sanitized_local_records(self):
        self._with_trade_review_log(
            [
                {
                    "id": "r2",
                    "created_at": "2026-06-10T10:00:00",
                    "ticker": "002008.SZ",
                    "user_decision": "观察",
                    "overall_action": "等待",
                    "authorization": "Bearer SHOULD_DROP",
                    "user_note": "不要追高",
                }
            ]
        )

        response = self.client.get("/api/trade-review/cache").json()

        self.assertTrue(response["ok"])
        packet = response["data"]
        self.assertEqual(packet["packet_key"], "command_center_3_trade_review_cache")
        self.assertEqual(packet["status"], "ready")
        self.assertEqual(packet["record_count"], 1)
        self.assertEqual(packet["records"][0]["ticker"], "002008.SZ")
        self.assertNotIn("authorization", packet["records"][0])
        self.assertNotIn("SHOULD_DROP", json.dumps(response, ensure_ascii=False))
        self.assertFalse(packet["external_calls_triggered"])
        self.assertTrue(packet["does_not_modify_strategy_action"])

    def test_quant_cache_endpoint_returns_cached_quant_without_external_work(self):
        self._with_snapshot_cache(
            {
                "quant_packet": {
                    "status": "ready",
                    "score": 71,
                    "confidence": "中",
                    "action_state": "只观察",
                    "authorization": "Bearer SHOULD_DROP",
                }
            }
        )

        response = self.client.get("/api/quant/cache").json()

        self.assertTrue(response["ok"])
        packet = response["data"]
        self.assertEqual(packet["packet_key"], "command_center_3_quant_backtest_cache")
        self.assertEqual(packet["status"], "ready")
        self.assertEqual(packet["quant_packet"]["score"], 71)
        self.assertNotIn("authorization", packet["quant_packet"])
        self.assertNotIn("SHOULD_DROP", json.dumps(response, ensure_ascii=False))
        self.assertTrue(packet["policy"]["does_not_run_backtest"])
        self.assertFalse(packet["external_calls_triggered"])
        self.assertTrue(packet["does_not_execute_trades"])

    def test_strategy_trace_cache_endpoint_returns_strategy_trace_without_external_work(self):
        self._with_snapshot_cache(
            {
                "strategy_packet": {
                    "status": "ready",
                    "action": "等待",
                    "confidence": "中",
                    "summary": "本地规则等待",
                    "authorization": "Bearer SHOULD_DROP",
                },
                "decision_packet": {
                    "status": "ready",
                    "overall_action": "只观察",
                    "api_key": "SHOULD_DROP",
                },
            }
        )

        response = self.client.get("/api/strategy/cache").json()

        self.assertTrue(response["ok"])
        packet = response["data"]
        self.assertEqual(packet["packet_key"], "command_center_3_strategy_trace_cache")
        self.assertEqual(packet["status"], "ready")
        self.assertEqual(packet["action_summary"]["action"], "等待")
        self.assertEqual(packet["decision_summary"]["overall_action"], "只观察")
        self.assertNotIn("SHOULD_DROP", json.dumps(response, ensure_ascii=False))
        self.assertTrue(packet["policy"]["does_not_call_tushare"])
        self.assertTrue(packet["policy"]["does_not_call_deepseek"])
        self.assertFalse(packet["external_calls_triggered"])
        self.assertTrue(packet["does_not_execute_trades"])
        self.assertTrue(packet["does_not_modify_strategy_action"])

    def test_position_context_cache_endpoint_returns_position_without_external_work(self):
        self._with_snapshot_cache(
            {
                "holding_action": {
                    "ticker": "002008.SZ",
                    "shares": 1200,
                    "cost": 105,
                    "current_price": 111,
                    "action_state": "只观察",
                    "authorization": "Bearer SHOULD_DROP",
                },
                "position_risk_budget": {"risk_level": "中"},
                "today_action": {"overall_action": "只观察"},
                "strategy_packet": {"action": "等待"},
            }
        )

        response = self.client.get("/api/position/cache").json()

        self.assertTrue(response["ok"])
        packet = response["data"]
        self.assertEqual(packet["packet_key"], "command_center_3_position_context_cache")
        self.assertEqual(packet["status"], "ready")
        self.assertEqual(packet["position_summary"]["ticker"], "002008.SZ")
        self.assertEqual(packet["holding_action"]["shares"], 1200)
        self.assertNotIn("SHOULD_DROP", json.dumps(response, ensure_ascii=False))
        self.assertTrue(packet["policy"]["does_not_call_tushare"])
        self.assertTrue(packet["policy"]["does_not_recalculate_position"])
        self.assertFalse(packet["external_calls_triggered"])
        self.assertTrue(packet["does_not_execute_trades"])
        self.assertTrue(packet["does_not_modify_strategy_action"])
        self.assertTrue(packet["does_not_modify_holdings"])

    def test_evidence_cache_endpoint_returns_lineage_without_external_work(self):
        self._with_snapshot_cache(
            {
                "a_share_fact_lineage_summary": {
                    "schema_version": "a_share_fact_lineage_summary.v1",
                    "summary": "已验证 1｜阻断 0｜缓存 0｜过期 0｜缺失 0｜待验证 0",
                    "items": [{"fact_key": "moneyflow", "status_label": "已验证", "enters_core_action": False}],
                    "counts": {"verified": 1, "blocked": 0, "missing": 0, "cached": 0},
                }
            }
        )

        response = self.client.get("/api/evidence/cache").json()

        self.assertTrue(response["ok"])
        packet = response["data"]
        self.assertEqual(packet["packet_key"], "command_center_3_a_share_evidence_cache")
        self.assertEqual(packet["mode"], "cache_only")
        self.assertEqual(packet["counts"]["lineage_verified"], 1)
        self.assertFalse(packet["external_calls_triggered"])
        self.assertFalse(packet["policy"]["lineage_enters_core_action"])
        self.assertTrue(packet["does_not_execute_trades"])

    def test_data_capability_cache_endpoint_returns_safe_local_status(self):
        self._with_snapshot_cache(
            {
                "data_capability": {
                    "items": [
                        {
                            "provider": "Tushare",
                            "api": "margin_detail",
                            "label": "融资融券",
                            "capability_state": "permission_denied",
                            "status": "权限不足",
                            "authorization": "Bearer SHOULD_DROP",
                        }
                    ]
                }
            }
        )

        response = self.client.get("/api/data-capability/cache").json()

        self.assertTrue(response["ok"])
        packet = response["data"]
        self.assertEqual(packet["packet_key"], "command_center_3_data_capability_cache")
        self.assertEqual(packet["mode"], "cache_only")
        self.assertGreaterEqual(packet["counts"]["restricted"], 1)
        self.assertNotIn("SHOULD_DROP", json.dumps(response, ensure_ascii=False))
        self.assertFalse(packet["external_calls_triggered"])
        self.assertTrue(packet["policy"]["does_not_ping_tushare"])
        self.assertTrue(packet["does_not_execute_trades"])

    def test_post_task_stub_returns_task_id(self):
        self._with_meta_store()
        clear_task_statuses_for_tests(clear_persisted=True)
        created = self.client.post("/api/factor-quant/refresh-data", json={"ts_code": "002008.SZ"}).json()
        self.assertTrue(created["ok"])
        task_id = created["data"]["task_id"]
        self.assertTrue(task_id.startswith("local-"))

        status = self.client.get(f"/api/tasks/{task_id}").json()
        self.assertTrue(status["ok"])
        self.assertEqual(status["data"]["status"], "success")
        self.assertEqual(status["data"]["progress"], 1.0)
        self.assertEqual(status["data"]["call_ledger"][0]["call_status"], "stub_not_called")

        listing = self.client.get("/api/tasks").json()
        self.assertTrue(listing["ok"])
        self.assertEqual(listing["data"]["tasks"][0]["task_id"], task_id)
        task_service._TASKS.clear()
        persisted_status = self.client.get(f"/api/tasks/{task_id}").json()
        self.assertTrue(persisted_status["ok"])
        self.assertEqual(persisted_status["data"]["task_id"], task_id)
        self.assertEqual(persisted_status["data"]["backend"], "local_fallback")

    def test_run_light_endpoint_writes_factor_cache(self):
        self._with_meta_store()
        self._with_parquet_root()
        clear_task_statuses_for_tests(clear_persisted=True)
        self._with_snapshot_cache(
            {
                "timestamp": "2026-06-10T09:30:00",
                "moneyflow_packet": {"status": "ready", "ticker": "002008.SZ", "main_net_yi": 1.2},
                "strategy_packet": {"status": "ready", "action": "wait"},
                "decision_packet": {"status": "ready"},
                "quant_packet": {"status": "ready"},
            }
        )
        created = self.client.post("/api/factor-quant/run-light", json={"ts_code": "002008.SZ", "token": "DROP"}).json()
        self.assertTrue(created["ok"])
        task = created["data"]["task"]
        self.assertEqual(task["status"], "success")
        self.assertEqual(task["current_step"], "factor_light_completed_from_local_cache")
        self.assertEqual(task["call_ledger"][0]["call_status"], "cache_read")
        self.assertIn("local_parquet_factor_values", {item.get("api") for item in task["call_ledger"]})
        self.assertNotIn("token", task["payload_safe"])

        factor = self.client.get("/api/factor-quant/cache").json()
        self.assertTrue(factor["ok"])
        self.assertEqual(factor["data"]["mode"], "light")
        self.assertEqual(factor["data"]["cache_source"], "sqlite_meta")
        self.assertFalse(factor["data"]["external_calls_triggered"])
        self.assertEqual(factor["data"]["factor_values_storage"]["dataset"], "factor_values")
        self.assertFalse(factor["data"]["governance"]["allow_core_action"])

    def test_deepseek_explain_endpoint_is_guarded_and_sanitized(self):
        self._with_meta_store()
        clear_task_statuses_for_tests(clear_persisted=True)

        created = self.client.post(
            "/api/factor-quant/deepseek-explain",
            json={
                "provided_explanation": {
                    "summary": "整理摘要",
                    "support_notes": ["支持说明"],
                    "price": 100,
                    "strategy_action": "buy",
                    "factor_values": [1, 2],
                }
            },
        ).json()
        self.assertTrue(created["ok"])
        task = created["data"]["task"]
        self.assertEqual(task["status"], "success")
        self.assertEqual(task["call_ledger"][0]["call_status"], "provided_payload_sanitized")
        self.assertEqual(task["payload_safe"], {"provided_explanation_payload": True})
        self.assertFalse(task["deepseek_called"])
        self.assertFalse(task["external_calls_triggered"])

        factor = self.client.get("/api/factor-quant/cache").json()
        self.assertTrue(factor["ok"])
        explanation = factor["data"]["deepseek_explanation"]
        self.assertFalse(factor["data"]["deepseek_called"])
        self.assertEqual(explanation["payload"]["summary"], "整理摘要")
        self.assertIn("price", explanation["ignored_keys"])
        self.assertIn("strategy_action", explanation["ignored_keys"])
        self.assertIn("factor_values", explanation["ignored_keys"])
        self.assertFalse(factor["data"]["governance"]["allow_core_action"])
        self.assertTrue(factor["data"]["next_session_bridge"]["does_not_modify_action"])


if __name__ == "__main__":
    unittest.main()
