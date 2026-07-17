from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class UiStylesTrustedBindingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.main = (ROOT / "desktop/src/main.tsx").read_text(encoding="utf-8")
        cls.home = (ROOT / "desktop/src/routes/CommandCenterHome.tsx").read_text(encoding="utf-8")
        cls.candidate = (ROOT / "desktop/src/routes/CandidateRadar.tsx").read_text(encoding="utf-8")
        cls.runner = (ROOT / "scripts/streamlit_retirement_packaged_qa_runner.mjs").read_text(encoding="utf-8")
        cls.service = (ROOT / "server/services/streamlit_retirement_evidence_service.py").read_text(encoding="utf-8")

    def test_route_css_is_loaded_once_outside_ordinary_route_import_contract(self) -> None:
        for relative in (
            "./components/ProductSurface.css",
            "./routes/CommandCenterHome.css",
            "./routes/CandidateRadar.css",
            "./routes/FactorQuantHub.css",
            "./routes/NextSessionMap.css",
            "./routes/MarginEtf.css",
            "./routes/QmtReplayLab.css",
        ):
            self.assertEqual(self.main.count(f'import "{relative}";'), 1)
        self.assertNotIn('import "./CommandCenterHome.css";', self.home)
        self.assertNotIn('import "./CandidateRadar.css";', self.candidate)
        factor = (ROOT / "desktop/src/routes/FactorQuantHub.tsx").read_text(encoding="utf-8")
        self.assertNotIn('import "./FactorQuantHub.css";', factor)
        next_session = (ROOT / "desktop/src/routes/NextSessionMap.tsx").read_text(encoding="utf-8")
        self.assertNotIn('import "./NextSessionMap.css";', next_session)
        margin_etf = (ROOT / "desktop/src/routes/MarginEtf.tsx").read_text(encoding="utf-8")
        self.assertNotIn('import "./MarginEtf.css";', margin_etf)
        qmt_replay = (ROOT / "desktop/src/routes/QmtReplayLab.tsx").read_text(encoding="utf-8")
        self.assertNotIn('import "./QmtReplayLab.css";', qmt_replay)

    def test_all_product_styles_are_bound_by_both_trust_layers(self) -> None:
        for relative in (
            "desktop/src/main.tsx",
            "desktop/src/styles.css",
            "desktop/src/components/ProductSurface.css",
            "desktop/src/routes/CommandCenterHome.css",
            "desktop/src/routes/commandCenterHomeResultBinding.js",
            "desktop/src/routes/CandidateRadar.css",
            "desktop/src/routes/FactorQuantHub.css",
            "desktop/src/routes/NextSessionMap.css",
            "desktop/src/routes/nextSessionOrdinaryGate.ts",
            "desktop/src/routes/MarginEtf.css",
            "desktop/src/routes/QmtReplayLab.css",
            "desktop/src/routes/qmtReplayOrdinaryGate.ts",
        ):
            self.assertIn(f'"{relative}"', self.runner)
            self.assertIn(f'Path("{relative}")', self.service)


if __name__ == "__main__":
    unittest.main()
