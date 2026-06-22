import unittest
from pathlib import Path


class BackendOfflineNoticeGuidanceTests(unittest.TestCase):
    def test_backend_offline_notice_points_to_local_launcher_without_external_work(self):
        root = Path(__file__).resolve().parents[1]
        notice = (
            root / "desktop" / "src" / "components" / "BackendOfflineNotice.tsx"
        ).read_text(encoding="utf-8")

        self.assertIn("本地后端未连接", notice)
        self.assertIn("下一步：请使用桌面快捷方式或本地启动器重新打开 Command Center 3.0", notice)
        self.assertIn("启动器会等待 FastAPI 和页面都 ready 后才打开入口", notice)
        self.assertIn("当前画面只显示离线保护状态", notice)
        self.assertIn("连接地址：{apiBase}", notice)
        self.assertIn("不会调用 Tushare、DeepSeek 或 GitHub", notice)
        self.assertIn("不会执行真实交易，也不会修改 strategy action", notice)
        self.assertNotIn("fetch(", notice)
        self.assertNotIn("TUSHARE_TOKEN", notice)
        self.assertNotIn("DEEPSEEK_API_KEY", notice)
        self.assertNotIn("GITHUB_TOKEN", notice)


if __name__ == "__main__":
    unittest.main()
