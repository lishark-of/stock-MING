from __future__ import annotations

import unittest
from pathlib import Path


class CallLedgerAuditWorktreeSurfaceTests(unittest.TestCase):
    def setUp(self) -> None:
        root = Path(__file__).resolve().parents[1]
        self.page = (root / "desktop" / "src" / "routes" / "CallLedgerAudit.tsx").read_text(
            encoding="utf-8"
        )

    def test_local_worktree_clean_gate_is_visible_without_paths(self) -> None:
        self.assertIn("local_worktree_cleanliness_audit", self.page)
        self.assertIn("localWorktreeCleanlinessAudit", self.page)
        self.assertIn("localWorktreeStatusCodeRows", self.page)
        self.assertIn("Local worktree clean gate", self.page)
        self.assertIn("只读 git status --short 计数", self.page)
        self.assertIn("不输出文件路径、不代表 CI 状态", self.page)
        self.assertIn("local_git_status_short_no_github_api_no_push", self.page)
        self.assertIn("worktree_clean", self.page)
        self.assertIn("dirty_file_count", self.page)
        self.assertIn("tracked_change_count", self.page)
        self.assertIn("untracked_file_count", self.page)
        self.assertIn("raw_paths_emitted", self.page)
        self.assertIn("raw_status_lines_emitted", self.page)
        self.assertIn("clean worktree 是生成当前 HEAD 本地 gate receipt 的最后卫生门槛", self.page)

    def test_worktree_gate_keeps_push_and_ci_boundaries_visible(self) -> None:
        self.assertIn("blocks_local_push_gate_receipt", self.page)
        self.assertIn("release_hygiene_blocker", self.page)
        self.assertIn("did_not_push", self.page)
        self.assertIn("github_api_called", self.page)
        self.assertIn("不是 provider/model/trading 失败，也不是远端 CI 状态", self.page)
        self.assertIn("Local push gate run receipt", self.page)
        self.assertIn("不代表远端 CI", self.page)


if __name__ == "__main__":
    unittest.main()
