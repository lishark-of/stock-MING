from __future__ import annotations

import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from scripts import next_session_map_contract
from server.services import next_session_service, packet_service


class NextSessionContractProcessIsolationTests(unittest.TestCase):
    def test_build_contract_does_not_replace_runtime_sqlite_paths(self):
        original_packet_path = packet_service.SQLITE_META_PATH
        original_next_path = next_session_service.SQLITE_META_PATH

        with tempfile.TemporaryDirectory() as temp_dir:
            runtime_path = Path(temp_dir) / "runtime.sqlite"
            packet_service.SQLITE_META_PATH = runtime_path
            next_session_service.SQLITE_META_PATH = runtime_path
            try:
                with next_session_map_contract._EXACT_PACKETS_CACHE_LOCK:
                    next_session_map_contract._EXACT_PACKETS_CACHE = None
                with ThreadPoolExecutor(max_workers=4) as pool:
                    contracts = list(pool.map(lambda _: next_session_map_contract.build_contract(), range(4)))

                self.assertTrue(all(contract["contract_ready"] for contract in contracts))
                self.assertEqual(packet_service.SQLITE_META_PATH, runtime_path)
                self.assertEqual(next_session_service.SQLITE_META_PATH, runtime_path)
            finally:
                packet_service.SQLITE_META_PATH = original_packet_path
                next_session_service.SQLITE_META_PATH = original_next_path


if __name__ == "__main__":
    unittest.main()
