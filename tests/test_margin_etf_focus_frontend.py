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

    def test_focus_precedes_default_closed_technical_details(self):
        self.assertIn('aria-label="ETF 融资普通用户摘要"', self.focus)
        self.assertIn('aria-label="ETF 融资研究与技术详情"', self.details)
        self.assertNotIn(" open", self.details.split(">", 1)[0])
        self.assertIn("完整候选表、回放操作、记录和审计信息默认收起", self.details)

    def test_focus_has_five_plain_categories_and_one_next_step(self):
        self.assertEqual(self.focus.count('data-focus-category="'), 5)
        for category in ("cash-risk", "core-etfs", "guardrails", "freshness", "next-step"):
            self.assertIn(f'data-focus-category="{category}"', self.focus)
        self.assertEqual(self.focus.count("<a "), 1)
        self.assertNotIn("DataLineageTable", self.focus)
        self.assertNotIn("TaskStatusPanel", self.focus)
        self.assertNotIn("call_ledger", self.focus)
        self.assertNotIn("<button", self.focus)

    def test_validator_recomputes_source_projection_scope_projection_and_binding(self):
        for required in (
            "canonicalSha256(sourceProjection)",
            "sourceIdentity.source_projection_sha256",
            "sourceIdentity.result_version !== `margin-etf-source:${sourceProjectionHash}`",
            "scopeHash !== sourceIdentity.scope_hash",
            "canonicalSha256(projection)",
            "computedProjectionHash !== projectionHash",
            "canonicalSha256({",
            "computedBindingHash !== bindingHash",
            'sourceIdentity.task_type !== "refresh_margin_etf_local_packets"',
            'sourceIdentity.source !== "margin_etf_local_packet_replay.v1"',
            "Math.max(Date.parse(etfUpdated), Date.parse(marginUpdated)) > Date.parse(ledgerUpdated)",
            "Date.parse(ledgerUpdated) > Date.parse(snapshotUpdated)",
            "strictDecimal",
        ):
            self.assertIn(required, self.page)

    def test_runtime_digest_and_time_truth_table_fails_closed(self):
        runner = textwrap.dedent(
            r"""
            const { createRequire } = await import('node:module');
            const { readFileSync } = await import('node:fs');
            const { webcrypto } = await import('node:crypto');
            if (!globalThis.crypto) globalThis.crypto = webcrypto;
            const require = createRequire(import.meta.url);
            const ts = require('./desktop/node_modules/typescript');
            const source = readFileSync('desktop/src/routes/MarginEtf.tsx', 'utf8');
            const start = source.indexOf('// MARGIN_ETF_FOCUS_VALIDATOR_START');
            const end = source.indexOf('// MARGIN_ETF_FOCUS_VALIDATOR_END');
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
            const safety = {...Object.fromEntries(falseFields.map((field)=>[field,false])),does_not_execute_trades:true,does_not_modify_strategy_action:true};
            const canonical = value => {
              if (value === null || typeof value === 'boolean' || typeof value === 'string' || typeof value === 'number') return JSON.stringify(value);
              if (Array.isArray(value)) return `[${value.map(canonical).join(',')}]`;
              const keys = Object.keys(value).sort();
              return `{${keys.map((key)=>`${JSON.stringify(key)}:${canonical(value[key])}`).join(',')}}`;
            };
            const sha = async value => Buffer.from(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(canonical(value)))).toString('hex');
            const build = async (times={}) => {
              const target = '002008.SZ';
              const dataDate = '20260717';
              const etfUpdated = times.etf ?? '2026-07-17T10:00:00+08:00';
              const marginUpdated = times.margin ?? '2026-07-17T10:00:01+08:00';
              const ledgerUpdated = times.ledger ?? '2026-07-17T10:01:00+08:00';
              const snapshotUpdated = times.snapshot ?? '2026-07-17T10:02:00+08:00';
              const core = [{code:'510300.SH',name:'沪深300ETF',reason:'宽基研究样本'}];
              const sourceProjection = {
                schema_version:'margin_etf_source_projection.v1',target,packet_keys:['command_center_etf_packet','command_center_margin_packet'],
                etf:{status:'ready',data_status:'ready',data_date:dataDate,updated_at:etfUpdated,source:'ETF local cache',verification_status:'已验证',
                  available_cash:'128000',recommended_cash_ratio:'22',current_margin_ratio:'9',recommended_margin_ratio:'10',allow_new_margin:false,
                  recommended_etfs:core,safety,warnings:[]},
                margin:{status:'ready',data_status:'ready',trade_date:dataDate,updated_at:marginUpdated,source:'margin local cache',verification_status:'已验证',
                  financing_balance_yi:'12.3',financing_buy_yi:'1.2',margin_balance_yi:'14.5',safety,warnings:[]}
              };
              const sourceHash = await sha(sourceProjection);
              const sourceVersion = `margin-etf-source:${sourceHash}`;
              const scopeHash = await sha({route:'POST /api/market/margin-etf-local-refresh',mode:'local_packet_replay',
                requested_packet_keys:['command_center_etf_packet','command_center_margin_packet'],target,
                source_identity:'margin_etf_local_packet_replay.v1',source_result_version:sourceVersion,source_projection_sha256:sourceHash});
              const identity = {task_id:'local-task-1',task_type:'refresh_margin_etf_local_packets',scope_hash:scopeHash,target,
                source:'margin_etf_local_packet_replay.v1',result_version:sourceVersion,source_projection_sha256:sourceHash,
                ledger_sha256:'1'.repeat(64),ledger_fetched_at:ledgerUpdated};
              const projection = {schema_version:'margin_etf_focus_projection.v2',source_identity:identity,data_date:dataDate,
                expected_trade_date:dataDate,freshness_state:'fresh',calendar_validated:true,
                packet_updated_at:{etf:etfUpdated,margin:marginUpdated,ledger:ledgerUpdated,snapshot:snapshotUpdated},
                source_labels:{etf:'ETF local cache',margin:'margin local cache'},
                etf:{status:'ready',data_status:'ready',verification_status:'已验证',available_cash:'128000',recommended_cash_ratio:'22',
                  current_margin_ratio:'9',recommended_margin_ratio:'10',allow_new_margin:false,core_etfs:core},
                margin:{status:'ready',data_status:'ready',verification_status:'已验证',financing_balance_yi:'12.3',financing_buy_yi:'1.2',margin_balance_yi:'14.5'}};
              const projectionHash = await sha(projection);
              const bindingHash = await sha({schema_version:'margin_etf_focus_binding.v2',producer:'command_center_home_snapshot.margin_etf_focus_binding',
                source_identity:identity,safety,projection,projection_sha256:projectionHash});
              return {schema_version:'margin_etf_focus_binding.v2',producer:'command_center_home_snapshot.margin_etf_focus_binding',
                producer_run_id:`home-snapshot:${bindingHash}`,result_version:`margin-etf:${bindingHash}`,binding_sha256:bindingHash,projection_sha256:projectionHash,
                source_identity:identity,etf_packet_key:'command_center_etf_packet',margin_packet_key:'command_center_margin_packet',data_date:dataDate,
                expected_trade_date:dataDate,freshness_state:'fresh',calendar_validated:true,same_margin_etf_packet_date_bound:true,usable_for_risk_budget:true,
                ...safety,projection};
            };
            const clone = value => structuredClone(value);
            const parse = async (left,right,overrides={}) => Boolean(await validator.parseMarginEtfFocusBinding({etfBinding:left,marginBinding:right,
              etfPacketKey:'command_center_etf_packet',marginPacketKey:'command_center_margin_packet',loading:false,error:'',...overrides}));
            const binding = await build();
            const results = {canonical:await parse(binding,clone(binding))};
            const cases = {
              fake_hash: (l,r)=>{l.binding_sha256='a'.repeat(64);r.binding_sha256='a'.repeat(64);l.producer_run_id='home-snapshot:'+l.binding_sha256;r.producer_run_id=l.producer_run_id;l.result_version='margin-etf:'+l.binding_sha256;r.result_version=l.result_version;return[l,r]},
              synchronized_value_mutation: (l,r)=>{l.projection.etf.available_cash='999999';r.projection.etf.available_cash='999999';return[l,r]},
              synchronized_source_mutation: (l,r)=>{l.source_identity.scope_hash='b'.repeat(64);r.source_identity.scope_hash='b'.repeat(64);l.projection.source_identity.scope_hash='b'.repeat(64);r.projection.source_identity.scope_hash='b'.repeat(64);return[l,r]},
              deepseek_true: (l,r)=>{l.deepseek_called=true;r.deepseek_called=true;return[l,r]},
              number_instead_of_canonical_decimal: (l,r)=>{l.projection.etf.available_cash=128000;r.projection.etf.available_cash=128000;return[l,r]},
              one_side_only: (l,r)=>{r.projection_sha256='c'.repeat(64);return[l,r]}
            };
            for (const [name,mutate] of Object.entries(cases)) {
              const [left,right]=mutate(clone(binding),clone(binding));
              results[name]=await parse(left,right);
            }
            const rollover = await build({etf:'2026-07-17T23:59:00+08:00',margin:'2026-07-17T23:59:10+08:00',ledger:'2026-07-17T23:59:30+08:00',snapshot:'2026-07-18T00:00:00+08:00'});
            results.rollover=await parse(rollover,clone(rollover));
            results.loading=await parse(binding,clone(binding),{loading:true});
            process.stdout.write(JSON.stringify(results));
            """
        )
        completed = subprocess.run(
            ["node", "--input-type=module", "-e", runner], cwd=ROOT, check=True, capture_output=True, text=True
        )
        results = json.loads(completed.stdout)
        self.assertTrue(results.pop("canonical"))
        self.assertEqual({name for name, accepted in results.items() if accepted}, set())

    def test_route_style_is_scoped_responsive_and_reduced_motion_safe(self):
        self.assertIn(".margin-etf-focus {", self.style)
        self.assertNotIn("body {", self.style)
        self.assertNotIn("#root {", self.style)
        self.assertIn("@media (max-width: 860px)", self.style)
        self.assertIn("@media (max-width: 520px)", self.style)
        self.assertIn("@media (prefers-reduced-motion: reduce)", self.style)
        self.assertIn("overflow-wrap: break-word", self.style)


if __name__ == "__main__":
    unittest.main()
