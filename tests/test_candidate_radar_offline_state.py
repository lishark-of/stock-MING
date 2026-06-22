import unittest
from pathlib import Path


class CandidateRadarOfflineStateTests(unittest.TestCase):
    def test_candidate_radar_uses_shared_page_state_banner_for_offline_cache(self):
        root = Path(__file__).resolve().parents[1]
        source = (
            root / "desktop" / "src" / "routes" / "CandidateRadar.tsx"
        ).read_text(encoding="utf-8")

        self.assertIn('import PageStateBanner from "../components/PageStateBanner";', source)
        self.assertIn("const [loading, setLoading] = useState(true)", source)
        self.assertIn('const [error, setError] = useState("")', source)
        self.assertIn('setError("")', source)
        self.assertIn('if (res.ok === false) setError(res.error ?? "candidate_radar_cache_not_ok")', source)
        self.assertIn(".catch((err) => setError(err instanceof Error ? err.message : String(err)))", source)
        self.assertIn(".finally(() => setLoading(false))", source)
        self.assertIn("const empty = !loading && !error && !Object.keys(cache).length", source)
        self.assertIn("<PageStateBanner", source)
        self.assertIn('emptyTitle="暂无下一票雷达本地缓存"', source)
        self.assertIn("雷达页只读取本地候选缓存", source)
        self.assertIn("不会在页面打开或 React 渲染中自动扫描全市场", source)
        self.assertNotIn("fetch(", source)
        self.assertNotIn("TUSHARE_TOKEN", source)
        self.assertNotIn("DEEPSEEK_API_KEY", source)
        self.assertNotIn("GITHUB_TOKEN", source)


if __name__ == "__main__":
    unittest.main()
