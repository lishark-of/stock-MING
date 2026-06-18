import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.services import candidate_service


class CandidateRadarWorkerFilesystemRoundtripSmokeTest(unittest.TestCase):
    def test_candidate_radar_task_roundtrips_through_local_filesystem_worker(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "scripts/candidate_radar_worker_filesystem_roundtrip_smoke.py",
                "--timeout",
                "30",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )

        self.assertEqual(result.returncode, 0, f"stdout={result.stdout}\nstderr={result.stderr}")
        payload = json.loads(result.stdout)
        self.assertEqual(
            payload["schema_version"],
            "candidate_radar_worker_filesystem_roundtrip_smoke.v1",
        )
        self.assertEqual(payload["status"], "candidate_radar_worker_filesystem_roundtrip_passed")
        self.assertEqual(
            payload["direct_evidence_layer"],
            "L3_local_candidate_radar_worker_filesystem_roundtrip_not_redis",
        )
        self.assertEqual(payload["candidate_task_type"], "run_candidate_radar_full_pool_local_scan")
        self.assertEqual(payload["output_packet_key"], "command_center_3_candidate_radar_cache")
        self.assertTrue(payload["celery_testing_worker_started"])
        self.assertTrue(payload["task_dispatched"])
        self.assertTrue(payload["task_result_returned"])
        self.assertTrue(payload["worker_backed_execution_done"])
        self.assertTrue(payload["worker_backed_local_full_pool_scan_done"])
        self.assertTrue(payload["worker_backed_local_deep_scan_fallback_done"])
        self.assertTrue(payload["filesystem_broker_used"])
        self.assertFalse(payload["redis_broker_used"])
        self.assertFalse(payload["redis_pinged"])
        self.assertFalse(payload["production_worker_complete"])
        self.assertFalse(payload["production_radar_replacement_complete"])
        self.assertFalse(payload["production_full_pool_scan_done"])
        self.assertFalse(payload["production_deep_scan_done"])
        self.assertFalse(payload["deepseek_model_execution_done"])
        self.assertFalse(payload["model_execution_implemented"])
        self.assertFalse(payload["provider_backed_acceptance_done"])
        self.assertFalse(payload["external_calls_triggered"])
        self.assertFalse(payload["tushare_called"])
        self.assertFalse(payload["deepseek_called"])
        self.assertFalse(payload["github_called"])
        self.assertTrue(payload["does_not_execute_trades"])
        self.assertTrue(payload["does_not_modify_strategy_action"])
        self.assertTrue(payload["candidate_is_not_buy_instruction"])
        self.assertFalse(payload["contains_secret"])
        self.assertEqual(payload["returned_task_status"], "success")
        self.assertEqual(payload["returned_current_step"], "candidate_radar_full_pool_local_scan_completed")
        self.assertEqual(payload["returned_call_api"], "local_candidate_radar_full_pool_local_scan")
        self.assertGreater(payload["returned_call_row_count"], 0)
        self.assertTrue(payload["returned_task_id"])
        self.assertEqual(payload["deep_scan_returned_task_status"], "success")
        self.assertEqual(payload["deep_scan_returned_current_step"], "candidate_radar_deep_scan_worker_fallback_ready")
        self.assertEqual(payload["deep_scan_returned_call_api"], "local_candidate_radar_deep_scan_worker_fallback")
        self.assertGreater(payload["deep_scan_returned_call_row_count"], 0)
        self.assertTrue(payload["deep_scan_returned_task_id"])

        old_evidence_path = candidate_service.CANDIDATE_WORKER_FILESYSTEM_ROUNDTRIP_EVIDENCE_PATH
        with tempfile.TemporaryDirectory(prefix="candidate_radar_worker_evidence_test_") as tmp:
            evidence_path = Path(tmp) / "candidate_radar_worker_filesystem_roundtrip_smoke.json"
            evidence_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            candidate_service.CANDIDATE_WORKER_FILESYSTEM_ROUNDTRIP_EVIDENCE_PATH = evidence_path
            try:
                packet = candidate_service.read_candidate_radar_cache()
            finally:
                candidate_service.CANDIDATE_WORKER_FILESYSTEM_ROUNDTRIP_EVIDENCE_PATH = old_evidence_path

        stage_manifest = packet["candidate_radar_production_stage_scope_manifest"]
        stage_rows = {row["stage_key"]: row for row in packet["candidate_radar_production_stage_scope_rows"]}
        direct_keys = set(stage_manifest["direct_evidence_stage_keys"])
        pending_keys = set(stage_manifest["pending_stage_keys"])
        self.assertIn("worker_transport_round_trip_smoke", direct_keys)
        self.assertIn("worker_full_pool_execution", direct_keys)
        self.assertIn("worker_deep_scan_execution", direct_keys)
        self.assertNotIn("worker_full_pool_execution", pending_keys)
        self.assertNotIn("worker_deep_scan_execution", pending_keys)
        for stage_key in ("worker_full_pool_execution", "worker_deep_scan_execution"):
            row = stage_rows[stage_key]
            self.assertTrue(row["direct_evidence_complete"])
            self.assertFalse(row["production_blocker"])
            self.assertTrue(row["worker_backed_execution_done"])
            self.assertTrue(row["worker_filesystem_roundtrip_evidence_present"])
            self.assertFalse(row["production_radar_replacement_complete"])
            self.assertFalse(row["provider_backed_acceptance_done"])
            self.assertFalse(row["full_pool_scan_done"])
            self.assertFalse(row["deep_scan_done"])
            self.assertFalse(row["external_calls_triggered"])
            self.assertFalse(row["tushare_called"])
            self.assertFalse(row["deepseek_called"])
            self.assertFalse(row["github_called"])
            self.assertTrue(row["does_not_execute_trades"])
            self.assertTrue(row["does_not_modify_strategy_action"])
            self.assertTrue(row["candidate_is_not_buy_instruction"])
