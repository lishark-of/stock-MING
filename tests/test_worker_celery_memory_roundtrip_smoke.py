import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class WorkerCeleryMemoryRoundtripSmokeTest(unittest.TestCase):
    def test_memory_roundtrip_smoke_returns_direct_non_redis_evidence(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "scripts/worker_celery_memory_roundtrip_smoke.py",
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
        self.assertEqual(payload["schema_version"], "worker_celery_memory_roundtrip_smoke.v1")
        self.assertEqual(payload["status"], "celery_memory_roundtrip_passed")
        self.assertEqual(payload["direct_evidence_layer"], "L3_local_celery_memory_roundtrip_not_redis")
        self.assertTrue(payload["celery_testing_worker_started"])
        self.assertTrue(payload["task_dispatched"])
        self.assertTrue(payload["task_result_returned"])
        self.assertFalse(payload["redis_broker_used"])
        self.assertFalse(payload["redis_pinged"])
        self.assertFalse(payload["production_worker_complete"])
        self.assertFalse(payload["external_calls_triggered"])
        self.assertFalse(payload["tushare_called"])
        self.assertFalse(payload["deepseek_called"])
        self.assertFalse(payload["github_called"])
        self.assertTrue(payload["does_not_execute_trades"])
        self.assertTrue(payload["does_not_modify_strategy_action"])
        self.assertFalse(payload["contains_secret"])
        self.assertEqual(payload["returned_payload"]["payload_mode"], "memory_roundtrip")
