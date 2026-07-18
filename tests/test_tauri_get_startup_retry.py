import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLIENT = ROOT / "desktop" / "src" / "api" / "client.ts"


class TauriGetStartupRetryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = CLIENT.read_text(encoding="utf-8")

    def test_retry_is_tauri_only_get_only_and_bounded(self) -> None:
        source = self.source
        self.assertIn('"__TAURI_INTERNALS__" in window', source)
        self.assertIn('method === "GET" && isTauriRuntime()', source)
        self.assertIn("TAURI_GET_STARTUP_RETRY_ATTEMPTS = 40", source)
        self.assertIn("TAURI_GET_STARTUP_RETRY_DELAY_MS = 500", source)
        self.assertIn(
            "await waitForLocalBackend(Math.min(TAURI_GET_STARTUP_RETRY_DELAY_MS, remainingStartupMs))",
            source,
        )
        self.assertIn("if (remainingStartupMs <= 0) break", source)
        self.assertNotIn('method === "POST" && isTauriRuntime()', source)

    def test_retry_only_follows_local_connection_failure(self) -> None:
        source = self.source
        request_start = source.index("async function request<T>")
        request_end = source.index("function queryString", request_start)
        request = source[request_start:request_end]

        self.assertIn("connectionFailed = true", request)
        self.assertIn("if (!connectionFailed || attempt + 1 >= startupAttemptCount) break", request)
        self.assertIn("return { ok: false", request)
        self.assertIn("API_BASE_CANDIDATES", request)
        self.assertNotIn("Tushare", request)
        self.assertNotIn("DeepSeek", request)
        self.assertNotIn("strategy action", request)


if __name__ == "__main__":
    unittest.main()
