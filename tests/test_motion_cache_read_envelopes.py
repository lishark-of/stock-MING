from __future__ import annotations

import copy
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from server.main import app
from server.schemas.packets import cache_read_call_ledger, cache_read_packet
from server.services import packet_service


class MotionCacheReadEnvelopeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    @staticmethod
    def _packet(schema: str, packet_key: str, *, historical_api: str) -> dict:
        return {
            "schema_version": schema,
            "packet_key": packet_key,
            "status": "ready",
            "external_calls_triggered": False,
            "tushare_called": False,
            "deepseek_called": False,
            "github_called": False,
            "does_not_execute_trades": True,
            "does_not_modify_strategy_action": True,
            "call_ledger": [
                {
                    "api": historical_api,
                    "request_method": "POST",
                    "external": True,
                    "external_calls_triggered": True,
                    "tushare_called": True,
                    "does_not_execute_trades": True,
                    "does_not_modify_strategy_action": True,
                }
            ],
            "warnings": [],
        }

    def _assert_current_read_envelope(
        self,
        *,
        route: str,
        patch_target: str,
        packet: dict,
        expected_api: str,
        expected_route: str,
    ) -> dict:
        packet_before = copy.deepcopy(packet)
        with patch(patch_target, return_value=packet):
            response = self.client.get(route)
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(len(payload["call_ledger"]), 1)
        current = payload["call_ledger"][0]
        self.assertEqual(current["api"], expected_api)
        self.assertEqual(current["source"], expected_route)
        self.assertEqual(current["route"], expected_route)
        self.assertEqual(current["request_method"], "GET")
        for field in (
            "external",
            "external_calls_triggered",
            "provider_or_model_calls",
            "provider_called",
            "model_called",
            "worker_called",
            "tushare_called",
            "deepseek_called",
            "github_called",
            "trade_called",
            "trading_called",
            "broker_called",
            "order_called",
            "real_trading_enabled",
            "contains_secret",
        ):
            self.assertIs(current[field], False)
        self.assertIs(current["does_not_execute_trades"], True)
        self.assertIs(current["does_not_modify_strategy_action"], True)
        self.assertEqual(payload["data"]["cache_call_ledger"], payload["call_ledger"])
        self.assertEqual(payload["data"]["call_ledger"], packet["call_ledger"])
        self.assertTrue(payload["data"]["call_ledger"][0]["tushare_called"])
        for field in (
            "external",
            "external_calls_triggered",
            "provider_or_model_calls",
            "provider_called",
            "model_called",
            "worker_called",
            "tushare_called",
            "deepseek_called",
            "github_called",
            "trade_called",
            "trading_called",
            "broker_called",
            "order_called",
            "real_trading_enabled",
            "contains_secret",
        ):
            self.assertIs(payload["data"][field], False)
        self.assertIs(payload["data"]["does_not_execute_trades"], True)
        self.assertIs(payload["data"]["does_not_modify_strategy_action"], True)
        self.assertEqual(packet, packet_before)
        return payload

    def test_motion_cache_routes_separate_current_get_from_historical_provenance(self) -> None:
        cases = (
            (
                "/api/desktop/preflight-cache",
                "server.api.routes_desktop.desktop_service.read_desktop_shell_preflight_cache",
                self._packet("desktop_shell_preflight_cache.v1", "command_center_3_desktop_shell_preflight_cache", historical_api="local_tauri_package_artifact_review"),
                "local_desktop_shell_preflight_cache",
                "GET /api/desktop/preflight-cache",
            ),
            (
                "/api/factor-quant/cache",
                "server.api.routes_factor_quant.factor_service.read_factor_quant_cache",
                self._packet("factor_quant_hub.v1", "command_center_factor_quant_hub_packet", historical_api="trade_cal"),
                "local_factor_quant_cache",
                "GET /api/factor-quant/cache",
            ),
            (
                "/api/next-session/cache",
                "server.api.routes_next_session.next_session_service.read_next_session_cache",
                self._packet("next_session_projection.v1", "command_center_next_session_projection_packet", historical_api="local_next_session_browser_qa_review"),
                "local_next_session_cache",
                "GET /api/next-session/cache",
            ),
            (
                "/api/worker/cache",
                "server.api.routes_worker.worker_service.read_worker_runtime_cache",
                self._packet("worker_runtime_cache.v1", "command_center_3_worker_runtime_cache", historical_api="local_worker_production_promotion_review"),
                "local_worker_runtime_cache",
                "GET /api/worker/cache",
            ),
        )
        for route, patch_target, packet, expected_api, expected_route in cases:
            with self.subTest(route=route):
                payload = self._assert_current_read_envelope(
                    route=route,
                    patch_target=patch_target,
                    packet=packet,
                    expected_api=expected_api,
                    expected_route=expected_route,
                )
                self.assertEqual(payload["data"]["schema_version"], packet["schema_version"])

    def test_factor_preserves_authoritative_current_row_metadata(self) -> None:
        packet = self._packet(
            "factor_quant_hub.v1",
            "command_center_factor_quant_hub_packet",
            historical_api="trade_cal",
        )
        packet["cache_call_ledger"] = [
            {
                "api": "local_factor_quant_cache",
                "request_params_safe": {"status": "ready", "cache_source": "sqlite"},
                "row_count": 37,
                "data_date": "20260710",
                "call_status": "cache_read",
            }
        ]
        payload = self._assert_current_read_envelope(
            route="/api/factor-quant/cache",
            patch_target="server.api.routes_factor_quant.factor_service.read_factor_quant_cache",
            packet=packet,
            expected_api="local_factor_quant_cache",
            expected_route="GET /api/factor-quant/cache",
        )
        current = payload["call_ledger"][0]
        self.assertEqual(current["row_count"], 37)
        self.assertEqual(current["data_date"], "20260710")
        self.assertEqual(current["request_params_safe"]["cache_source"], "sqlite")

    def test_cache_read_helpers_do_not_alias_or_mutate_nested_input(self) -> None:
        packet = self._packet(
            "factor_quant_hub.v1",
            "command_center_factor_quant_hub_packet",
            historical_api="trade_cal",
        )
        existing = [{"api": "local_factor_quant_cache", "row_count": 3, "request_params_safe": {"status": "ready"}}]
        before = copy.deepcopy(packet)
        ledger = cache_read_call_ledger(
            api="local_factor_quant_cache",
            route="GET /api/factor-quant/cache",
            packet=packet,
            existing=existing,
        )
        response_packet = cache_read_packet(packet, cache_call_ledger=ledger)
        self.assertIsNot(response_packet, packet)
        self.assertIsNot(response_packet["cache_call_ledger"], ledger)
        self.assertIsNot(response_packet["cache_call_ledger"][0], ledger[0])
        response_packet["cache_call_ledger"][0]["request_params_safe"]["status"] = "changed"
        self.assertEqual(ledger[0]["request_params_safe"]["status"], "ready")
        self.assertEqual(packet, before)

    def test_desktop_alias_binds_exact_current_route_without_mutating_history(self) -> None:
        packet = self._packet(
            "desktop_shell_preflight_cache.v1",
            "command_center_3_desktop_shell_preflight_cache",
            historical_api="local_tauri_package_artifact_review",
        )
        self._assert_current_read_envelope(
            route="/api/desktop/preflight",
            patch_target="server.api.routes_desktop.desktop_service.read_desktop_shell_preflight_cache",
            packet=packet,
            expected_api="local_desktop_shell_preflight_cache",
            expected_route="GET /api/desktop/preflight",
        )

    def test_next_session_cache_missing_keeps_current_get_ledger_and_canonical_schema(self) -> None:
        packet = self._packet(
            "next_session_projection.v1",
            "command_center_next_session_projection_packet",
            historical_api="local_next_session_production_promotion_review",
        )
        packet.update({"status": "cache_missing", "cache_source": "cache_missing"})
        with patch(
            "server.api.routes_next_session.next_session_service.read_next_session_cache",
            return_value=packet,
        ):
            response = self.client.get("/api/next-session/cache")
        payload = response.json()
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["data"]["schema_version"], "next_session_projection.v1")
        self.assertEqual(payload["error"]["code"], "cache_missing")
        self.assertEqual(payload["error"]["details"]["route"], "GET /api/next-session/cache")
        self.assertEqual([row["api"] for row in payload["call_ledger"]], ["local_next_session_cache"])
        self.assertEqual(payload["call_ledger"][0]["call_status"], "cache_missing")
        self.assertEqual(payload["call_ledger"][0]["row_count"], 0)
        self.assertEqual(payload["data"]["status"], "cache_missing")
        self.assertEqual(payload["data"]["cache_source"], "cache_missing")
        self.assertEqual(payload["data"]["call_ledger"], packet["call_ledger"])

    def test_real_next_session_builder_uses_canonical_schema_when_cache_is_missing(self) -> None:
        with (
            patch("server.services.packet_service._read_persisted_packet", return_value=None),
            patch("server.services.packet_service._read_snapshot_packet", return_value=None),
            patch("server.services.packet_service.load_snapshot_cache", return_value={}),
        ):
            packet = packet_service.build_next_session_cache()
        self.assertEqual(packet["status"], "cache_missing")
        self.assertEqual(packet["cache_source"], "cache_missing")
        self.assertEqual(packet["schema_version"], "next_session_projection.v1")


if __name__ == "__main__":
    unittest.main()
