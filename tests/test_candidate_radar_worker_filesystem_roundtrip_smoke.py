import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class CandidateRadarWorkerFilesystemRoundtripSmokeTest(unittest.TestCase):
    def test_candidate_radar_task_roundtrips_through_local_filesystem_worker(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "scripts/candidate_radar_worker_filesystem_roundtrip_smoke.py",
                "--timeout",
                "10",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
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
