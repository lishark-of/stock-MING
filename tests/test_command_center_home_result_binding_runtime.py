import json
from pathlib import Path
import subprocess
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "desktop" / "src" / "routes" / "commandCenterHomeResultBinding.js"


class CommandCenterHomeResultBindingRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        script = textwrap.dedent(
            f"""
            import {{
              hasUnconfirmedHomeSymbolEdit,
              makeStrictHomeConfirmedChain,
              makeStrictHomeResultBinding,
              sameOrdinaryHomeResultBinding,
              selectMatchingHomeConfirmedChain,
              selectMatchingHomeResultBinding,
              strictHomeIdentity,
              strictHomeResultDate,
              strictHomeSymbol,
            }} from {json.dumps(MODULE.as_uri())};

            const currentFields = {{
              symbol: "current_result_symbol",
              taskId: "current_result_task_id",
              resultVersion: "current_result_version",
              dataDate: "current_result_data_date",
              freshness: "current_result_freshness_state",
            }};
            const lineageFields = {{
              symbol: "symbol",
              taskId: "task_id",
              resultVersion: "result_version",
              dataDate: "data_date",
              freshness: "freshness_state",
            }};
            const complete = {{
              symbol: "000001.SZ",
              task_id: "task-1",
              result_version: "qrv_1",
              data_date: "20260717",
              freshness_state: "fresh_provider",
            }};
            const matchingSummary = {{
              current_result_symbol: "000001.SZ",
              current_result_task_id: "task-1",
              current_result_version: "qrv_1",
              current_result_data_date: "20260717",
              current_result_freshness_state: "fresh_provider",
            }};
            const summaryBinding = makeStrictHomeResultBinding(matchingSummary, currentFields, "candidate");
            const lineageBinding = makeStrictHomeResultBinding(complete, lineageFields, "candidate");
            const freshnessConflict = makeStrictHomeResultBinding(
              {{...complete, freshness_state: "current"}},
              lineageFields,
              "storage",
            );
            const partialSummary = makeStrictHomeResultBinding(
              {{current_result_symbol: "000001.SZ"}},
              currentFields,
              "candidate",
            );
            const partialLineage = makeStrictHomeResultBinding(
              {{task_id: "task-B", result_version: "qrv_B", data_date: "20260717", freshness_state: "fresh"}},
              lineageFields,
              "candidate",
            );
            const confirmedFields = {{symbol: "symbol", taskId: "task_id"}};
            const confirmedA = makeStrictHomeConfirmedChain(
              {{symbol: "000001.SZ", task_id: "task-1"}},
              confirmedFields,
              "checkpoint",
            );
            const confirmedB = makeStrictHomeConfirmedChain(
              {{symbol: "600519.SH", task_id: "task-2"}},
              confirmedFields,
              "receipt",
            );

            console.log(JSON.stringify({{
              dates: {{
                compact: strictHomeResultDate("20260717"),
                iso_expected: strictHomeResultDate("2026-07-17", {{allowIsoDate: true}}),
                iso_result_rejected: strictHomeResultDate("2026-07-17"),
                wrapped_rejected: strictHomeResultDate("x2026-07-17y", {{allowIsoDate: true}}),
                impossible_rejected: strictHomeResultDate("20260230"),
                number_rejected: strictHomeResultDate(20260717),
              }},
              identities: {{
                symbol: strictHomeSymbol("000001.SZ"),
                lower_symbol_rejected: strictHomeSymbol("000001.sz"),
                object_symbol_rejected: strictHomeSymbol({{value: "000001.SZ"}}),
                numeric_task_rejected: strictHomeIdentity(42),
              }},
              sources: {{
                matching: selectMatchingHomeResultBinding([summaryBinding, lineageBinding]),
                partials_do_not_splice: selectMatchingHomeResultBinding([partialSummary, partialLineage]),
                freshness_equal: sameOrdinaryHomeResultBinding(summaryBinding, freshnessConflict),
                freshness_conflict: selectMatchingHomeResultBinding([summaryBinding, freshnessConflict]),
              }},
              confirmed: {{
                partial_does_not_splice: makeStrictHomeConfirmedChain(
                  {{symbol: "000001.SZ"}},
                  confirmedFields,
                  "partial",
                ),
                conflict: selectMatchingHomeConfirmedChain([confirmedA, confirmedB]),
              }},
              edits: {{
                untouched: hasUnconfirmedHomeSymbolEdit({{touched: false, raw: "", valid: false, normalized: "", confirmedSymbol: "000001.SZ"}}),
                cleared: hasUnconfirmedHomeSymbolEdit({{touched: true, raw: "", valid: false, normalized: "", confirmedSymbol: "000001.SZ"}}),
                invalid: hasUnconfirmedHomeSymbolEdit({{touched: true, raw: "abc", valid: false, normalized: "", confirmedSymbol: "000001.SZ"}}),
                changed: hasUnconfirmedHomeSymbolEdit({{touched: true, raw: "600519", valid: true, normalized: "600519.SH", confirmedSymbol: "000001.SZ"}}),
                same: hasUnconfirmedHomeSymbolEdit({{touched: true, raw: "000001", valid: true, normalized: "000001.SZ", confirmedSymbol: "000001.SZ"}}),
              }},
            }}));
            """
        )
        completed = subprocess.run(
            ["node", "--input-type=module", "--eval", script],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        cls.result = json.loads(completed.stdout)

    def test_dates_are_validated_without_coercion(self) -> None:
        self.assertEqual(self.result["dates"]["compact"], "20260717")
        self.assertEqual(self.result["dates"]["iso_expected"], "20260717")
        for key in ("iso_result_rejected", "wrapped_rejected", "impossible_rejected", "number_rejected"):
            self.assertEqual(self.result["dates"][key], "")

    def test_identity_fields_reject_wrong_shapes_and_types(self) -> None:
        self.assertEqual(self.result["identities"]["symbol"], "000001.SZ")
        self.assertEqual(self.result["identities"]["lower_symbol_rejected"], "")
        self.assertEqual(self.result["identities"]["object_symbol_rejected"], "")
        self.assertEqual(self.result["identities"]["numeric_task_rejected"], "")

    def test_sources_must_be_individually_complete_and_equal(self) -> None:
        self.assertFalse(self.result["sources"]["matching"]["conflict"])
        self.assertEqual(self.result["sources"]["matching"]["binding"]["taskId"], "task-1")
        self.assertIsNone(self.result["sources"]["partials_do_not_splice"]["binding"])
        self.assertFalse(self.result["sources"]["partials_do_not_splice"]["conflict"])
        self.assertFalse(self.result["sources"]["freshness_equal"])
        self.assertTrue(self.result["sources"]["freshness_conflict"]["conflict"])
        self.assertIsNone(self.result["sources"]["freshness_conflict"]["binding"])

    def test_confirmed_chain_never_splices_or_silently_picks_a_conflict(self) -> None:
        self.assertIsNone(self.result["confirmed"]["partial_does_not_splice"])
        self.assertTrue(self.result["confirmed"]["conflict"]["conflict"])
        self.assertIsNone(self.result["confirmed"]["conflict"]["chain"])

    def test_touched_empty_or_invalid_input_remains_fail_closed(self) -> None:
        self.assertFalse(self.result["edits"]["untouched"])
        self.assertTrue(self.result["edits"]["cleared"])
        self.assertTrue(self.result["edits"]["invalid"])
        self.assertTrue(self.result["edits"]["changed"])
        self.assertFalse(self.result["edits"]["same"])


if __name__ == "__main__":
    unittest.main()
