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
              isCanonicalHomeResultFreshness,
              makeStrictHomeConfirmedChain,
              makeStrictHomeResultBinding,
              sameOrdinaryHomeResultBinding,
              selectMatchingHomeConfirmedChain,
              selectMatchingHomeResultBinding,
              shouldKeepHomeResultPending,
              shouldShowHomeSupportingDetails,
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
            const fourMatchingBindings = [
              summaryBinding,
              lineageBinding,
              {{...summaryBinding, source: "canonical_summary"}},
              {{...lineageBinding, source: "canonical_lineage"}},
            ];
            const missingSurfaceTruthTable = fourMatchingBindings.map((_, missingIndex) =>
              selectMatchingHomeResultBinding(
                fourMatchingBindings.map((binding, index) => index === missingIndex ? null : binding),
              ),
            );
            const conflictingBindingByField = Object.fromEntries(
              [
                ["symbol", "600519.SH"],
                ["taskId", "task-2"],
                ["resultVersion", "qrv_2"],
                ["dataDate", "20260716"],
                ["freshness", "fresh"],
              ].map(([field, value]) => [
                field,
                selectMatchingHomeResultBinding([
                  summaryBinding,
                  {{...summaryBinding, [field]: value, source: `conflict_${{field}}`}},
                ]),
              ]),
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
                complete_four: selectMatchingHomeResultBinding(fourMatchingBindings),
                complete_plus_missing: selectMatchingHomeResultBinding([summaryBinding, null]),
                missing_surface_truth_table: missingSurfaceTruthTable,
                conflicting_field_truth_table: conflictingBindingByField,
                partials_do_not_splice: selectMatchingHomeResultBinding([partialSummary, partialLineage]),
                freshness_equal: sameOrdinaryHomeResultBinding(summaryBinding, freshnessConflict),
                freshness_conflict: selectMatchingHomeResultBinding([summaryBinding, freshnessConflict]),
              }},
              freshness: {{
                fresh: isCanonicalHomeResultFreshness("fresh"),
                fresh_provider: isCanonicalHomeResultFreshness("fresh_provider"),
                current: isCanonicalHomeResultFreshness("current"),
                today: isCanonicalHomeResultFreshness("today"),
                validated_current: isCanonicalHomeResultFreshness("validated_current"),
                wrapped: isCanonicalHomeResultFreshness(" fresh "),
              }},
              pending: {{
                none: shouldKeepHomeResultPending({{pendingSymbol: "", pendingTaskId: "", binding: summaryBinding}}),
                before_task_id: shouldKeepHomeResultPending({{pendingSymbol: "000001.SZ", pendingTaskId: "", binding: summaryBinding}}),
                old_binding: shouldKeepHomeResultPending({{pendingSymbol: "600519.SH", pendingTaskId: "task-2", binding: summaryBinding}}),
                wrong_task: shouldKeepHomeResultPending({{pendingSymbol: "000001.SZ", pendingTaskId: "task-2", binding: summaryBinding}}),
                exact_new_binding: shouldKeepHomeResultPending({{pendingSymbol: "000001.SZ", pendingTaskId: "task-1", binding: summaryBinding}}),
              }},
              details: {{
                visible: shouldShowHomeSupportingDetails({{binding: summaryBinding, inputGateClosed: false}}),
                hidden_for_input: shouldShowHomeSupportingDetails({{binding: summaryBinding, inputGateClosed: true}}),
                hidden_without_binding: shouldShowHomeSupportingDetails({{binding: null, inputGateClosed: false}}),
              }},
              confirmed: {{
                partial_does_not_splice: makeStrictHomeConfirmedChain(
                  {{symbol: "000001.SZ"}},
                  confirmedFields,
                  "partial",
                ),
                conflict: selectMatchingHomeConfirmedChain([confirmedA, confirmedB]),
                matching: selectMatchingHomeConfirmedChain([
                  confirmedA,
                  {{...confirmedA, source: "writeback"}},
                ]),
                missing: selectMatchingHomeConfirmedChain([confirmedA, null]),
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
        self.assertFalse(self.result["sources"]["matching"]["incomplete"])
        self.assertEqual(self.result["sources"]["matching"]["binding"]["taskId"], "task-1")
        self.assertIsNotNone(self.result["sources"]["complete_four"]["binding"])
        self.assertFalse(self.result["sources"]["complete_four"]["incomplete"])
        self.assertIsNone(self.result["sources"]["complete_plus_missing"]["binding"])
        self.assertTrue(self.result["sources"]["complete_plus_missing"]["incomplete"])
        for resolution in self.result["sources"]["missing_surface_truth_table"]:
            self.assertIsNone(resolution["binding"])
            self.assertTrue(resolution["incomplete"])
        for resolution in self.result["sources"]["conflicting_field_truth_table"].values():
            self.assertIsNone(resolution["binding"])
            self.assertTrue(resolution["conflict"])
        self.assertIsNone(self.result["sources"]["partials_do_not_splice"]["binding"])
        self.assertFalse(self.result["sources"]["partials_do_not_splice"]["conflict"])
        self.assertTrue(self.result["sources"]["partials_do_not_splice"]["incomplete"])
        self.assertFalse(self.result["sources"]["freshness_equal"])
        self.assertTrue(self.result["sources"]["freshness_conflict"]["conflict"])
        self.assertIsNone(self.result["sources"]["freshness_conflict"]["binding"])

    def test_only_canonical_exact_freshness_states_are_accepted(self) -> None:
        self.assertTrue(self.result["freshness"]["fresh"])
        self.assertTrue(self.result["freshness"]["fresh_provider"])
        for state in ("current", "today", "validated_current", "wrapped"):
            self.assertFalse(self.result["freshness"][state])

    def test_post_success_waits_for_the_exact_new_result_binding(self) -> None:
        self.assertFalse(self.result["pending"]["none"])
        self.assertTrue(self.result["pending"]["before_task_id"])
        self.assertTrue(self.result["pending"]["old_binding"])
        self.assertTrue(self.result["pending"]["wrong_task"])
        self.assertFalse(self.result["pending"]["exact_new_binding"])

    def test_supporting_details_share_the_authoritative_input_gate(self) -> None:
        self.assertTrue(self.result["details"]["visible"])
        self.assertFalse(self.result["details"]["hidden_for_input"])
        self.assertFalse(self.result["details"]["hidden_without_binding"])

    def test_confirmed_chain_never_splices_or_silently_picks_a_conflict(self) -> None:
        self.assertIsNone(self.result["confirmed"]["partial_does_not_splice"])
        self.assertTrue(self.result["confirmed"]["conflict"]["conflict"])
        self.assertIsNone(self.result["confirmed"]["conflict"]["chain"])
        self.assertFalse(self.result["confirmed"]["matching"]["incomplete"])
        self.assertIsNotNone(self.result["confirmed"]["matching"]["chain"])
        self.assertTrue(self.result["confirmed"]["missing"]["incomplete"])
        self.assertIsNone(self.result["confirmed"]["missing"]["chain"])

    def test_touched_empty_or_invalid_input_remains_fail_closed(self) -> None:
        self.assertFalse(self.result["edits"]["untouched"])
        self.assertTrue(self.result["edits"]["cleared"])
        self.assertTrue(self.result["edits"]["invalid"])
        self.assertTrue(self.result["edits"]["changed"])
        self.assertFalse(self.result["edits"]["same"])


if __name__ == "__main__":
    unittest.main()
