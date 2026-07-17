from __future__ import annotations

import threading
import unittest

from server.services.request_local_memo import (
    memoize_request_local_read,
    request_local_memo_scope,
)


class RequestLocalMemoTests(unittest.TestCase):
    def test_read_is_reused_only_within_one_scope(self) -> None:
        call_count = 0

        @memoize_request_local_read("sample")
        def read_sample() -> dict[str, int]:
            nonlocal call_count
            call_count += 1
            return {"generation": call_count}

        @request_local_memo_scope
        def build() -> tuple[dict[str, int], dict[str, int]]:
            return read_sample(), read_sample()

        first_a, first_b = build()
        second_a, second_b = build()

        self.assertIs(first_a, first_b)
        self.assertIs(second_a, second_b)
        self.assertIsNot(first_a, second_a)
        self.assertEqual(1, first_a["generation"])
        self.assertEqual(2, second_a["generation"])
        self.assertEqual(2, call_count)

    def test_calls_outside_scope_are_not_cached(self) -> None:
        call_count = 0

        @memoize_request_local_read("outside")
        def read_sample() -> int:
            nonlocal call_count
            call_count += 1
            return call_count

        self.assertEqual(1, read_sample())
        self.assertEqual(2, read_sample())

    def test_exception_is_not_cached(self) -> None:
        call_count = 0

        @memoize_request_local_read("retry")
        def read_sample() -> str:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("expected")
            return "ready"

        @request_local_memo_scope
        def build() -> str:
            with self.assertRaisesRegex(RuntimeError, "expected"):
                read_sample()
            return read_sample()

        self.assertEqual("ready", build())
        self.assertEqual(2, call_count)

    def test_concurrent_scopes_do_not_share_values(self) -> None:
        barrier = threading.Barrier(2)
        lock = threading.Lock()
        call_count = 0
        results: list[tuple[int, int]] = []

        @memoize_request_local_read("concurrent")
        def read_sample() -> int:
            nonlocal call_count
            with lock:
                call_count += 1
                value = call_count
            barrier.wait(timeout=2)
            return value

        @request_local_memo_scope
        def build() -> tuple[int, int]:
            return read_sample(), read_sample()

        threads = [threading.Thread(target=lambda: results.append(build())) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=3)

        self.assertTrue(all(not thread.is_alive() for thread in threads))
        self.assertEqual(2, call_count)
        self.assertEqual(2, len(results))
        self.assertTrue(all(first == second for first, second in results))
        self.assertEqual({1, 2}, {first for first, _ in results})

    def test_argument_calls_fall_through_without_cache(self) -> None:
        call_count = 0

        @memoize_request_local_read("arguments")
        def read_sample(value: int = 0) -> int:
            nonlocal call_count
            call_count += 1
            return value + call_count

        @request_local_memo_scope
        def build() -> tuple[int, int]:
            return read_sample(10), read_sample(10)

        self.assertEqual((11, 12), build())


if __name__ == "__main__":
    unittest.main()
