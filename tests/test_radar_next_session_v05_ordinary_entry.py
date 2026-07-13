import unittest
from pathlib import Path


class RadarNextSessionV05OrdinaryEntryTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[1]
        self.radar = (root / "desktop" / "src" / "routes" / "CandidateRadar.tsx").read_text(encoding="utf-8")
        self.next_map = (root / "desktop" / "src" / "routes" / "NextSessionMap.tsx").read_text(encoding="utf-8")

    def test_supplied_pool_summary_precedes_candidate_review_details(self):
        summary = self.radar.index('aria-label="candidate radar supplied pool ordinary readback"')
        compass = self.radar.index('aria-label="candidate radar ordinary candidate review compass"')
        supplied_pool = self.radar[summary:compass]

        self.assertLess(summary, compass)
        self.assertIn("suppliedPoolOrdinarySentence", supplied_pool)
        self.assertIn("MetricGrid items={suppliedPoolOrdinaryItems}", supplied_pool)
        for field in (
            "candidate_radar_v05_runtime",
            "candidate_radar_v05_bucket_counts",
            "candidate_radar_v05_coverage",
            "candidate_radar_v05_result_version",
            "candidateV05StageRows",
            "Candidate current/last-good",
        ):
            self.assertIn(field, self.radar)
        self.assertIn("不把本地 batch 说成全市场或 Celery production", supplied_pool)
        self.assertIn("候选不是买入指令", supplied_pool)
        self.assertNotIn("onClick=", supplied_pool)
        self.assertNotIn("postCandidateRadar", supplied_pool)

    def test_same_packet_readback_and_chart_focus_are_read_only(self):
        summary = self.next_map.index('aria-label="next session same packet ordinary readback"')
        chart = self.next_map.index('id="next-session-chart"')
        readback_end = self.next_map.index('aria-label="next session post confirm one minute chart read"', summary)
        readback = self.next_map[summary:readback_end]
        chart_region = self.next_map[chart:self.next_map.index("<details id=\"next-session-audit\"", chart)]

        self.assertIn("nextSessionSamePacketSentence", readback)
        self.assertIn("MetricGrid items={ordinaryNextMetricItems(nextSessionSamePacketItems)}", readback)
        for field in (
            "candidateRadarSameTaskFactModelReady",
            "candidateRadarSourceTaskLabel",
            "candidateRadarFreshnessLabel",
            "candidateRadarLastGoodLabel",
            "chartSummary.is_exact_next_session_packet",
        ):
            self.assertIn(field, self.next_map)
        self.assertIn('tabIndex={0}', chart_region)
        self.assertIn('aria-describedby="next-session-chart-keyboard-hint"', chart_region)
        self.assertIn("图表支持 hover", chart_region)
        self.assertIn("不会创建 task、修改价格、持仓或操作区", chart_region)
        self.assertNotIn("onClick=", readback)
        self.assertNotIn("postTask(", readback)


if __name__ == "__main__":
    unittest.main()
