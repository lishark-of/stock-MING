import json
import subprocess
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "desktop" / "src" / "routes" / "MarginEtf.tsx"
STYLE = ROOT / "desktop" / "src" / "routes" / "MarginEtf.css"


class MarginEtfFocusFrontendTests(unittest.TestCase):
    def setUp(self):
        self.page = PAGE.read_text(encoding="utf-8")
        self.style = STYLE.read_text(encoding="utf-8")
        focus_start = self.page.index('<section className="margin-etf-focus"')
        details_start = self.page.index('<details className="margin-etf-technical-details', focus_start)
        self.focus = self.page[focus_start:details_start]
        self.details = self.page[details_start:]

    def test_focus_precedes_one_default_closed_technical_details_container(self):
        self.assertIn('aria-label="ETF 融资普通用户摘要"', self.focus)
        self.assertIn('aria-label="ETF 融资研究与技术详情"', self.details)
        opening_tag = self.details.split(">", 1)[0]
        self.assertNotIn(" open", opening_tag)
        self.assertIn("完整候选表、回放操作、记录和审计信息默认收起", self.details)

    def test_focus_has_exactly_five_categories_and_one_next_step(self):
        self.assertEqual(self.focus.count('data-focus-category="'), 5)
        for category in ("cash-risk", "core-etfs", "guardrails", "freshness", "next-step"):
            self.assertIn(f'data-focus-category="{category}"', self.focus)
        self.assertEqual(self.focus.count("<a "), 1)
        self.assertIn('href={DATA_CAPABILITY_HREF}', self.focus)
        self.assertNotIn("<button", self.focus)
        self.assertNotIn("onClick=", self.focus)
        self.assertNotIn("postTask", self.focus)

    def test_focus_hides_engineering_language_and_full_tables(self):
        for forbidden in (
            "DataLineageTable",
            "TaskStatusPanel",
            "TaskLaunchReceipt",
            "call_ledger",
            "schema_version",
            "LTG",
            "P1",
            "P2",
            "P3",
        ):
            self.assertNotIn(forbidden, self.focus)
        self.assertIn("DataLineageTable", self.details)
        self.assertIn("TaskStatusPanel", self.details)

    def test_current_values_require_same_packet_date_and_freshness_binding(self):
        for required in (
            'MARGIN_ETF_FOCUS_SCHEMA_VERSION = "margin_etf_focus_binding.v2"',
            'MARGIN_ETF_FOCUS_PROJECTION_SCHEMA_VERSION = "margin_etf_focus_projection.v2"',
            'MARGIN_ETF_FOCUS_PRODUCER = "command_center_home_snapshot.margin_etf_focus_binding"',
            "same_margin_etf_packet_date_bound",
            '"command_center_etf_packet"',
            '"command_center_margin_packet"',
            "producer_run_id",
            "result_version",
            "binding_sha256",
            "projection_sha256",
            "source_identity",
            "data_date",
            "expected_trade_date",
            'etfBinding.freshness_state !== "fresh"',
            "etfBinding.calendar_validated !== true",
            "etfBinding.usable_for_risk_budget !== true",
            "parseMarginEtfFocusBinding",
            "marginEtfFocusView?.coreEtfs",
            "marginEtfFocusView.availableCash",
            "marginEtfFocusView.recommendedCashRatio",
            "marginEtfFocusView.allowNewMargin",
            "strictString",
            "strictYyyyMmDd",
            "strictNumber",
        ):
            self.assertIn(required, self.page)
        self.assertNotIn("etfPacket.result_binding", self.page)
        self.assertNotIn('["fresh", "current", "today"]', self.page)
        self.assertIn("marginEtfFocusCurrentEvidenceUsable", self.page)
        self.assertIn("当前不展示历史 ETF 名单", self.focus)
        self.assertIn("数据待确认；不开放融资判断", self.page)

    def test_runtime_binding_truth_table_fails_closed(self):
        runner = textwrap.dedent(
            """
            const { createRequire } = await import('node:module');
            const { readFileSync } = await import('node:fs');
            const require = createRequire(import.meta.url);
            const ts = require('./desktop/node_modules/typescript');
            const source = readFileSync('desktop/src/routes/MarginEtf.tsx', 'utf8');
            const start = source.indexOf('// MARGIN_ETF_FOCUS_VALIDATOR_START');
            const end = source.indexOf('// MARGIN_ETF_FOCUS_VALIDATOR_END');
            if (start < 0 || end <= start) throw new Error('validator markers missing');
            const moduleSource = source.slice(start, end);
            const js = ts.transpileModule(moduleSource, {
              compilerOptions: { module: ts.ModuleKind.ES2020, target: ts.ScriptTarget.ES2020 }
            }).outputText;
            const validator = await import('data:text/javascript;base64,' + Buffer.from(js).toString('base64'));

            const falseFields = [
              'external','external_calls_triggered','provider_or_model_calls','provider_called','model_called',
              'worker_called','tushare_called','deepseek_called','github_called','trade_called','trading_called',
              'broker_called','order_called','real_trading_enabled','contains_secret'
            ];
            const hash = 'a'.repeat(64);
            const identity = { task_id:'task-1', scope_hash:'b'.repeat(64), target:'002008.SZ', source:'source-1', result_version:'source-v1' };
            const projection = {
              schema_version:'margin_etf_focus_projection.v2', source_identity:identity,
              data_date:'20260717', expected_trade_date:'20260717', freshness_state:'fresh', calendar_validated:true,
              packet_updated_at:{etf:'2026-07-17T10:00:00',margin:'2026-07-17T10:00:01',snapshot:'2026-07-17T10:02:00'},
              source_labels:{etf:'ETF local cache',margin:'margin local cache'},
              etf:{status:'ready',data_status:'ready',verification_status:'已验证',available_cash:128000,
                recommended_cash_ratio:22,current_margin_ratio:9,recommended_margin_ratio:10,allow_new_margin:false,
                core_etfs:[{code:'510300.SH',name:'沪深300ETF',reason:'宽基研究样本'}]},
              margin:{status:'ready',data_status:'ready',verification_status:'已验证',financing_balance_yi:12.3,financing_buy_yi:1.2,margin_balance_yi:14.5}
            };
            const binding = {
              schema_version:'margin_etf_focus_binding.v2',producer:'command_center_home_snapshot.margin_etf_focus_binding',
              producer_run_id:'home-snapshot:'+hash,result_version:'margin-etf:'+hash,binding_sha256:hash,projection_sha256:'c'.repeat(64),
              source_identity:identity,etf_packet_key:'command_center_etf_packet',margin_packet_key:'command_center_margin_packet',
              data_date:'20260717',expected_trade_date:'20260717',freshness_state:'fresh',calendar_validated:true,
              same_margin_etf_packet_date_bound:true,usable_for_risk_budget:true,
              ...Object.fromEntries(falseFields.map((field)=>[field,false])),does_not_execute_trades:true,does_not_modify_strategy_action:true,
              projection
            };
            const clone = value => structuredClone(value);
            const parse = (etfBinding, marginBinding, overrides={}) => validator.parseMarginEtfFocusBinding({
              etfBinding, marginBinding, etfPacketKey:'command_center_etf_packet', marginPacketKey:'command_center_margin_packet',
              loading:false,error:'',...overrides
            });
            const results = { canonical: Boolean(parse(binding,clone(binding))) };
            const cases = {
              missing: (left,right) => [undefined,undefined],
              wrong_producer: (left,right) => { left.producer='attacker';right.producer='attacker';return [left,right]; },
              current_alias: (left,right) => { left.freshness_state='current';right.freshness_state='current';return [left,right]; },
              unsafe_external: (left,right) => { left.external_calls_triggered=true;right.external_calls_triggered=true;return [left,right]; },
              unsafe_trade: (left,right) => { left.does_not_execute_trades=false;right.does_not_execute_trades=false;return [left,right]; },
              boolean_cash: (left,right) => { left.projection.etf.available_cash=true;right.projection.etf.available_cash=true;return [left,right]; },
              boolean_ratio: (left,right) => { left.projection.etf.recommended_cash_ratio=true;right.projection.etf.recommended_cash_ratio=true;return [left,right]; },
              malformed_date: (left,right) => { left.data_date='stale-20260717';right.data_date='stale-20260717';return [left,right]; },
              mismatched_binding: (left,right) => { right.binding_sha256='d'.repeat(64);return [left,right]; },
              blank_candidate: (left,right) => { left.projection.etf.core_etfs=[{code:'',name:'',reason:''}];right.projection.etf.core_etfs=[{code:'',name:'',reason:''}];return [left,right]; }
            };
            for (const [name, mutate] of Object.entries(cases)) {
              const [left,right] = mutate(clone(binding),clone(binding));
              results[name] = Boolean(parse(left,right));
            }
            results.loading = Boolean(parse(binding,clone(binding),{loading:true}));
            results.error = Boolean(parse(binding,clone(binding),{error:'failed'}));
            process.stdout.write(JSON.stringify(results));
            """
        )
        completed = subprocess.run(
            ["node", "--input-type=module", "-e", runner],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        results = json.loads(completed.stdout)
        self.assertTrue(results.pop("canonical"))
        self.assertEqual({name for name, accepted in results.items() if accepted}, set())

    def test_focus_never_promotes_research_to_trading_or_financing_instruction(self):
        self.assertIn("研究结论不等于执行许可", self.focus)
        self.assertIn("不能把 ETF 候选、比例或强弱描述转换成买入、加仓、融资、下单或策略动作", self.focus)
        self.assertIn("当前不展示历史 ETF 名单，也不据此生成买入或融资动作", self.focus)
        self.assertNotIn("建议买入", self.focus)
        self.assertNotIn("立即融资", self.focus)

    def test_route_style_is_scoped_responsive_and_reduced_motion_safe(self):
        self.assertIn(".margin-etf-focus {", self.style)
        self.assertNotIn("body {", self.style)
        self.assertNotIn("#root {", self.style)
        self.assertIn("@media (max-width: 860px)", self.style)
        self.assertIn("@media (max-width: 520px)", self.style)
        self.assertIn("@media (prefers-reduced-motion: reduce)", self.style)
        self.assertIn("overflow-wrap: break-word", self.style)
        self.assertNotIn("overflow-wrap: anywhere", self.style)


if __name__ == "__main__":
    unittest.main()
