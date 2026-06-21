import unittest
from pathlib import Path


class CommandCenterMigrationPrincipleDocsTests(unittest.TestCase):
    def test_long_term_goals_record_no_blind_streamlit_copy_policy(self):
        root = Path(__file__).resolve().parents[1]
        text = (root / "docs" / "command_center_3_long_term_goals.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("Command Center 3.0 must not copy the old Streamlit app one-to-one", text)
        self.assertIn("preserving useful user capabilities", text)
        self.assertIn("does not mean copying legacy UI", text)
        self.assertIn("historical patchwork", text)

        for classification in ("`KEEP`", "`REDESIGN`", "`LEGACY-DEBUG`", "`RETIRE`"):
            self.assertIn(classification, text)

        self.assertIn("`KEEP` promotion requires direct Legacy Bug / UX Audit evidence", text)
        self.assertIn("observed user action or workflow problem", text)
        self.assertIn("legacy bug / confusing UX / patchwork path being removed", text)
        self.assertIn("data-lineage check", text)
        self.assertIn("replacement ordinary entrance", text)
        self.assertIn("frozen legacy path", text)
        self.assertIn("route inventory, legacy tab names, docs/config/scaffold", text)
        self.assertIn("cannot promote a module to `KEEP` by themselves", text)

        for entrance in (
            "今日作战台 / Daily Command Center",
            "股票量化推演 / Stock Quant Projection",
            "下一票雷达 / Candidate Radar",
        ):
            self.assertIn(entrance, text)

        for required_state in (
            "next user click",
            "Tushare/cache/DeepSeek/pending",
            "evidence is missing",
            "research-only and not a buy/sell instruction",
            "blocked or degraded",
            "last successful cache/result",
        ):
            self.assertIn(required_state, text)

        self.assertIn("shared ordinary source-state vocabulary", text)
        self.assertIn("`cache`, `Tushare`, `DeepSeek`, `pending`, `degraded`, and `last_successful_cache/result`", text)
        self.assertIn("`DeepSeek` means explanation-only and never a data source or action writer", text)
        self.assertIn("Showing these source-state chips is read-only UI guidance", text)
        self.assertIn("must not create tasks, call provider/model, write cache/config, or promote production evidence", text)
        self.assertIn("shared ordinary next-click rule", text)
        self.assertIn("one primary safe action per entrance", text)
        self.assertIn("visible disabled/degraded reason", text)
        self.assertIn("from a confirmed symbol to `生成 3.0 量化推演`", text)
        self.assertIn("Search typing, React render, mode banners, source-state chips, DeepSeek text, and radar candidates are not next-click actions", text)
        self.assertIn("Any next click that creates work must go through POST task / worker / local fallback", text)

        self.assertIn("fix push gate / CI", text)
        self.assertIn("rebuild LTG-13 Candidate Radar as a user-usable workflow", text)
        self.assertIn("searched-symbol -> `生成 3.0 量化推演`", text)
        self.assertIn("Do not add broad LTG contracts", text)
        self.assertIn("This strategy correction does not complete any LTG", text)
        self.assertIn("not production acceptance evidence", text)
        self.assertIn("必须在用户摘要区显示 `任务边界`", text)
        self.assertIn("并且早于 Settings / Developer / Audit 细节", text)
        self.assertIn("`GET cache` / React render 只读", text)
        self.assertIn("`manual` 或 `live_light` 补证只能走 `POST task` / worker / local fallback", text)
        self.assertIn("不在页面渲染中直连 Tushare、DeepSeek、GitHub 或交易路径", text)
        self.assertIn("不是 production evidence，也不代表完整 `live_light` 已实现", text)
        self.assertIn("`股票量化推演 / Stock Quant Projection` 的运行模式只读可见性必须与首页和雷达保持一致", text)
        self.assertIn("页面可从 `GET /api/bootstrap/status` 展示 `cache_only/manual/live_light/live_full` 当前口径", text)
        self.assertIn("不得因此创建 `live_light` bootstrap task、调用 provider/model、写配置、写 cache、泄露 token/key 或升级为 production evidence", text)
        self.assertIn("The same `runtime_mode_policy_rows` must carry config-owned boundary fields", text)
        self.assertIn("`cache_get_rule`", text)
        self.assertIn("`react_render_rule`", text)
        self.assertIn("`ledger_rule`", text)
        self.assertIn("`ordinary_entrance_visibility_rule`", text)
        self.assertIn("`ordinary_mode_banner_rule`", text)
        self.assertIn("`production_evidence_rule`", text)
        self.assertIn("require ordinary entrances to show `任务边界` before Settings / Developer / Audit details", text)
        self.assertIn("read-only status banner rather than a task launcher or config writer", text)
        self.assertIn("not proof that full `live_light` has been implemented", text)
        self.assertIn("Runtime config operator table", text)
        self.assertIn("owned by `config.py` and surfaced read-only through `GET /api/bootstrap/status`", text)
        self.assertIn("Source-switch intent for the future light research chain", text)
        self.assertIn("`true` is effective only in `live_light` after cache render and task gating", text)
        self.assertIn("Search typing, GET cache/status, FastAPI startup, and React render remain silent", text)
        self.assertIn("Default-off release switches for later provider/model task creation and frontend automation", text)
        self.assertIn("They stay effective false until execution-request, real ledgers, browser evidence, redaction, rollback, and promotion gates pass", text)
        self.assertIn("This table is config wording, not a new implementation claim", text)
        self.assertIn("prove legacy signal/capability parity, copy old Streamlit UI", text)
        self.assertIn("legacy signal/capability parity gaps are auditable without treating old Streamlit UI copy as a goal", text)
        self.assertIn("Full legacy signal/capability parity for the next-session chart is incomplete; visual/UI copy is not the target", text)
        self.assertIn("Compare retained next-session signal groups and interaction evidence against Legacy Bug / UX Audit findings", text)
        self.assertIn("old Streamlit UI copy outside the goal", text)
        self.assertNotIn("prove Streamlit parity", text)
        self.assertNotIn("Streamlit parity gaps", text)
        self.assertNotIn("Full parity with legacy Streamlit chart", text)
        self.assertNotIn("Compare against legacy Streamlit visual expectations", text)
        self.assertNotIn("future Streamlit-to-React comparison scope", text)

    def test_next_session_push_gate_contract_uses_signal_capability_parity_wording(self):
        root = Path(__file__).resolve().parents[1]
        text = (root / "scripts" / "next_session_map_contract.py").read_text(
            encoding="utf-8"
        )

        self.assertIn("legacy signal/capability parity review", text)
        self.assertIn("same-packet no-feature-loss evidence", text)
        self.assertIn("does not run a browser and does not refresh market data", text)
        self.assertNotIn("Streamlit parity", text)
        self.assertNotIn("legacy Streamlit parity", text)

    def test_migration_map_records_legacy_audit_and_five_commit_questions(self):
        root = Path(__file__).resolve().parents[1]
        text = (root / "docs" / "migration_map.md").read_text(encoding="utf-8")

        self.assertIn("## Legacy Bug / UX Audit Seed", text)
        self.assertIn("能力保留，不复制旧 Streamlit", text)
        self.assertIn("它不是完成审计，也不是生产验收证据", text)
        self.assertIn("## Ordinary Entrance Acceptance Map", text)
        self.assertIn("Legacy Bug / UX Audit 的覆盖锁定为普通旧工作流组", text)
        self.assertIn("home/daily command", text)
        self.assertIn("searched-symbol quant projection", text)
        self.assertIn("factor/risk/provider health", text)
        self.assertIn("discipline/backtest", text)
        self.assertIn("external brain/AI advisor", text)
        self.assertIn("`direct UX/bug evidence source`", text)
        self.assertIn("`ordinary entrance placement`", text)
        self.assertIn("`frozen legacy path`", text)
        self.assertIn(
            "| legacy workflow | classification | direct UX/bug evidence source | preserve user capability | remove / avoid from legacy | ordinary entrance placement | frozen legacy path |",
            text,
        )
        self.assertIn("seed-only；直接 UX/bug evidence pending before `KEEP`", text)
        self.assertIn("旧 Streamlit 首页按钮 / rerun flow 冻结，不搬 UI/state coupling", text)
        self.assertIn("旧同步单票作战室和 AI-as-action 文案冻结", text)
        self.assertIn("旧 fallback 雷达路径、推荐式文案和未证明性能路径冻结", text)
        self.assertIn("旧普通页 provider health 大表和自动探测路径冻结", text)
        self.assertIn("不迁移旧跨市场建议按钮；只允许重建为解释已有证据", text)
        self.assertIn("不能从 route inventory、legacy tab name、本地 receipt 或 no-feature-loss matrix 直接升级为 `KEEP`", text)
        self.assertIn("`KEEP` 提升门槛必须是直接审计证据", text)
        self.assertIn("observed user action / workflow problem", text)
        self.assertIn("被移除的 legacy bug / confusing UX / patchwork path", text)
        self.assertIn("data-lineage check", text)
        self.assertIn("replacement ordinary entrance", text)
        self.assertIn("frozen legacy path", text)
        self.assertIn("不能单独把旧模块升级为 `KEEP`", text)

        for classification in ("`REDESIGN`", "`LEGACY-DEBUG`", "`RETIRE`"):
            self.assertIn(classification, text)

        for entrance in (
            "今日作战台 / Daily Command Center",
            "股票量化推演 / Stock Quant Projection",
            "下一票雷达 / Candidate Radar",
        ):
            self.assertIn(entrance, text)

        self.assertIn("普通入口任务边界也必须留在用户摘要区", text)
        self.assertIn("都要在 Settings / Developer / Audit 细节之前显示 `任务边界`", text)
        self.assertIn("`GET cache` / React render 只读", text)
        self.assertIn("`manual` 或 `live_light` 补证只能走 `POST task` / worker / local fallback", text)
        self.assertIn("不在页面渲染中直连 Tushare、DeepSeek 或交易路径", text)
        self.assertIn("不是 production evidence，也不等于完整 `live_light` 已实现", text)
        self.assertIn("`runtime_mode_policy_rows` 也必须携带", text)
        self.assertIn("`cache_get_rule`", text)
        self.assertIn("`react_render_rule`", text)
        self.assertIn("`ledger_rule`", text)
        self.assertIn("`ordinary_entrance_visibility_rule`", text)
        self.assertIn("`ordinary_mode_banner_rule`", text)
        self.assertIn("`production_evidence_rule`", text)
        self.assertIn("普通入口 `任务边界` 早于 Settings / Developer / Audit", text)
        self.assertIn("ordinary mode banner 只是只读状态提示而不是 task launcher 或 config writer", text)
        self.assertIn("config policy row 不是 production evidence", text)
        self.assertIn("`config.COMMAND_CENTER_RUNTIME_CONFIG_NAMES` 为单一 allowlist 来源", text)
        self.assertIn("`runtime_config_names_source=config.COMMAND_CENTER_RUNTIME_CONFIG_NAMES`", text)
        self.assertIn("`runtime_config_names_match_reference_rows=true`", text)
        self.assertIn("`runtime_config_names_are_allowlisted=true`", text)
        self.assertIn("不能维护第二份 runtime config enum", text)
        self.assertIn("不能前端写回", text)
        self.assertIn("不能把 raw env dump 暴露成配置面板", text)
        self.assertIn("不能把配置表当成 `live_light` production evidence", text)
        self.assertIn("三入口的普通用户摘要必须共享 source-state chips", text)
        self.assertIn("`cache`、`Tushare`、`DeepSeek`、`pending`、`degraded`、`last_successful_cache/result`", text)
        self.assertIn("`DeepSeek` 只表示 explanation-only 且不是数据源或 action writer", text)
        self.assertIn("这些 chips 只是只读 UI 词表", text)
        self.assertIn("不创建 task、不调用 provider/model、不写 cache/config，也不是 production evidence", text)
        self.assertIn("三入口还必须共享 next-click 规则", text)
        self.assertIn("每个普通入口只突出一个主下一步动作", text)
        self.assertIn("blocked/degraded 时显示为什么不能点", text)
        self.assertIn("从已确认代码指向 `生成 3.0 量化推演`", text)
        self.assertIn("搜索输入、React render、mode banner、source-state chip、DeepSeek 文本和 radar candidate 都不是 next-click action", text)
        self.assertIn("任何会创建工作的 next click 都必须走 POST task / worker / local fallback", text)
        self.assertIn("`FactorQuantHub.tsx` 还只读读取 `GET /api/bootstrap/status`", text)
        self.assertIn("在普通用户量化推演摘要中展示 `cache_only/manual/live_light/live_full` 当前运行模式", text)
        self.assertIn("该可见性不创建 `POST /api/bootstrap/live-startup`、不调用 provider/model、不写配置或 cache、不泄露 token/key", text)
        self.assertIn("也不是 production evidence 或完整 `live_light` 实现", text)

        for question_fragment in (
            "保留了什么用户能力",
            "移除了什么旧 UX 问题",
            "哪条旧 bug / patchwork 路径没有迁移",
            "普通用户哪里更简单",
            "实际减少了哪个 blocker",
        ):
            self.assertIn(question_fragment, text)

        self.assertIn("不能进入普通入口", text)
        self.assertIn("LTG-13 的 no-feature-loss 只表示有用信号", text)
        self.assertIn("候选分组、扫描范围、证据链", text)
        self.assertIn("它不是旧雷达 UI parity", text)
        self.assertIn("不是旧 fallback 路径 parity", text)
        self.assertIn("不是把候选包装成买入推荐", text)
        self.assertIn("lineage 不清、已知 bug 或历史 patchwork", text)
        self.assertIn("不能用 no-feature-loss 作为照搬理由", text)
        self.assertIn("普通页只展示摘要和缺口；详细合同留在 Settings / Developer / Audit", text)
        self.assertNotIn("详细合同留在 developer/audit", text)
        self.assertIn("不证明 legacy signal/capability parity 或生产替代，也不代表复制旧 Streamlit 图表 UI", text)
        self.assertIn("性能 trace durable promotion、legacy signal/capability parity 和生产替代仍待验收", text)
        self.assertIn("旧 Streamlit 图表 UI/tab 复制不属于验收目标", text)
        self.assertIn("不能理解成复制旧 Streamlit 图表 UI 或旧 tab navigation", text)
        self.assertNotIn("不证明 Streamlit parity 或生产替代", text)
        self.assertNotIn("性能 trace durable promotion、Streamlit parity 和生产替代", text)

    def test_app_migration_plan_records_no_blind_copy_and_audit_gate(self):
        root = Path(__file__).resolve().parents[1]
        text = (root / "docs" / "app_migration_plan.md").read_text(encoding="utf-8")

        self.assertIn("Command Center 3.0 must not copy the old Streamlit app one-to-one", text)
        self.assertIn("preserving useful user capabilities", text)
        self.assertIn("does not mean copying legacy UI", text)
        self.assertIn("historical patchwork", text)
        self.assertIn("Legacy Bug / UX Audit", text)
        self.assertIn("`KEEP` promotion requires direct Legacy Bug / UX Audit evidence", text)
        self.assertIn("the specific legacy bug/confusing UX/patchwork path removed", text)
        self.assertIn("data-lineage check", text)
        self.assertIn("replacement ordinary entrance", text)
        self.assertIn("frozen legacy path", text)
        self.assertIn("cannot make a legacy module ordinary-user-ready by themselves", text)
        self.assertIn("Ordinary entrances should share one source-state chip vocabulary", text)
        self.assertIn("`cache`, `Tushare`, `DeepSeek`, `pending`, `degraded`, and `last_successful_cache/result`", text)
        self.assertIn("explanation-only model output", text)
        self.assertIn("Rendering these chips is read-only planning language", text)
        self.assertIn("must not create tasks, call provider/model, write cache/config, or promote production evidence", text)
        self.assertIn("Ordinary entrances should also share one next-click rule", text)
        self.assertIn("show one primary safe action", text)
        self.assertIn("show a clear disabled/degraded reason", text)
        self.assertIn("route a confirmed symbol to `生成 3.0 量化推演`", text)
        self.assertIn("must not behave as hidden next-click actions", text)
        self.assertIn("Any work-creating action remains POST task / worker / local fallback only", text)
        self.assertIn("each ordinary entrance must expose next click", text)
        self.assertIn("Tushare/cache/DeepSeek/pending source state", text)
        self.assertIn("research-only boundary that is not a buy/sell instruction", text)
        self.assertIn("missing evidence", text)
        self.assertIn("blocked/degraded state", text)
        self.assertIn("last successful cache/result", text)
        self.assertIn("普通入口任务边界 must stay visible in the user summary area", text)
        self.assertIn("show `任务边界` before Settings / Developer / Audit details", text)
        self.assertIn("`GET cache` / React render 只读", text)
        self.assertIn("`manual` 或 `live_light` 补证只能走 `POST task` / worker / local fallback", text)
        self.assertIn("must not directly call Tushare、DeepSeek、GitHub 或交易路径 during render", text)
        self.assertIn("not production evidence", text)
        self.assertIn("does not mean the full `live_light` workflow is implemented", text)
        self.assertIn("`股票量化推演 / Stock Quant Projection` may also show a read-only runtime-mode banner", text)
        self.assertIn("from `GET /api/bootstrap/status` in its ordinary summary", text)
        self.assertIn("using the same `cache_only/manual/live_light/live_full` vocabulary as the home and radar pages", text)
        self.assertIn("That banner is only a visibility aid", text)
        self.assertIn("must not create `POST /api/bootstrap/live-startup`", text)
        self.assertIn("call provider/model, write config/cache, expose token/key", text)
        self.assertIn("upgrade a local receipt into production evidence", text)
        self.assertIn("The migration plan references `runtime_mode_policy_rows`", text)
        self.assertIn("`cache_get_rule`", text)
        self.assertIn("`react_render_rule`", text)
        self.assertIn("`ledger_rule`", text)
        self.assertIn("`ordinary_entrance_visibility_rule`", text)
        self.assertIn("`ordinary_mode_banner_rule`", text)
        self.assertIn("`production_evidence_rule`", text)
        self.assertIn("ordinary-entry `任务边界` visibility before Settings / Developer / Audit", text)
        self.assertIn("ordinary mode banner read-only status display rather than task launching or config writing", text)
        self.assertIn("config policy rows remaining non-production evidence", text)
        self.assertIn("The operator-facing config口径 is", text)
        self.assertIn("server config is the source of truth", text)
        self.assertIn("read-only, non-editable, no-writeback, no-secret, and non-production evidence", text)
        self.assertIn("A configured source switch or release switch is not the same thing as an effective external call", text)
        self.assertIn("`cache_only` forces effective automation false even if every live switch is configured true", text)
        self.assertIn("`COMMAND_CENTER_LIVE_STARTUP_AUTOSTART`", text)
        self.assertIn("Local bootstrap task-create/reuse guard after cache render, not provider/model authorization", text)
        self.assertIn("`COMMAND_CENTER_LIVE_SEARCH_SUBMIT_AUTOSTART`", text)
        self.assertIn("Safe searched-symbol submit guard for local quant-projection receipt task, not search typing automation", text)
        self.assertIn("`COMMAND_CENTER_LIVE_ALLOW_FULL_POOL`", text)
        self.assertIn("no hidden `live_full` automation in this migration phase", text)
        self.assertIn("`KEEP` means useful and reliable enough to preserve with minimal redesign", text)
        self.assertIn("`REDESIGN` means useful capability but old UX/code should be rebuilt", text)
        self.assertIn("`LEGACY-DEBUG` means keep only for admin/debug/fallback", text)
        self.assertIn("`RETIRE` means freeze or remove from ordinary user workflow", text)

        for classification in ("`KEEP`", "`REDESIGN`", "`LEGACY-DEBUG`", "`RETIRE`"):
            self.assertIn(classification, text)

        for entrance in (
            "今日作战台 / Daily Command Center",
            "股票量化推演 / Stock Quant Projection",
            "下一票雷达 / Candidate Radar",
        ):
            self.assertIn(entrance, text)

        for question_fragment in (
            "what user capability was preserved",
            "what legacy UX problem was removed",
            "which legacy bug or patchwork path was intentionally not migrated",
            "what became simpler for a non-technical user",
            "which real blocker was reduced",
        ):
            self.assertIn(question_fragment, text)

        self.assertIn("not production acceptance evidence", text)
        self.assertIn("does not complete any LTG by itself", text)
        self.assertIn("Preserve runtime-mode automation boundaries", text)
        self.assertIn("Keep GET packet/cache endpoints read-only in every mode", text)
        self.assertIn("Allow `live_light` only for bounded local background task creation", text)
        self.assertIn("backtests, Tushare full scans, full-market scans", text)
        self.assertIn("Preserve useful capabilities, data sources, signals, evidence chains", text)
        self.assertIn("legacy workbench remains fallback/admin/debug", text)
        self.assertIn("Streamlit is retained as fallback/admin/debug", text)
        self.assertIn("must not be described as the primary 3.0 runtime surface", text)
        self.assertIn("not the primary 3.0 surface", text)
        self.assertIn("until the React/Tauri workflow is demonstrably easier", text)
        self.assertIn("Keep the research decision loop clear", text)
        self.assertIn("research-only strategy context", text)
        self.assertIn("explain existing evidence without issuing buy/sell instructions", text)
        self.assertIn("### Option A: pywebview + Streamlit fallback hardening", text)
        self.assertIn("fallback/admin/debug safety path", text)
        self.assertIn("must not become the ordinary-user migration target", text)
        self.assertIn("packet/API-backed 3.0 workflows", text)
        self.assertIn("Reuse boundary: service packets, data adapters, evidence chains", text)
        self.assertIn("radar signal definitions, and ETF research inputs can remain referenceable", text)
        self.assertIn("Streamlit rendering code, confusing navigation, buggy flows", text)
        self.assertIn("must not be reused as ordinary 3.0 UX", text)
        self.assertIn("high for fallback/admin/debug recovery only", text)
        self.assertIn("cannot prove the React/Tauri ordinary workflow is clearer or ready", text)
        self.assertIn("Long term: prioritize a Tauri + React + Python local API pilot around the three ordinary entrances", text)
        self.assertIn("prove those user paths are easier, clearer, and more reliable", text)
        self.assertIn("综合推演中心 2.0 is now a useful packetized evidence source and transition workspace", text)
        self.assertIn("not the target ordinary 3.0 UX", text)
        self.assertIn("recompose its useful packets into the three ordinary entrances", text)
        self.assertIn("Default into a clear 3.0 entry / transition screen", text)
        self.assertIn("not deeper Streamlit tab navigation", text)
        self.assertIn(
            "Keep the Streamlit UI reachable only as fallback/admin/debug",
            text,
        )
        self.assertIn("it is not the ordinary 3.0 UX target", text)
        self.assertIn("Redesign or freeze confusing legacy UX", text)
        self.assertIn("unclear data lineage", text)
        self.assertIn("before they enter an ordinary React/Tauri workflow", text)
        self.assertIn("Preserve useful research capabilities without promoting confusing legacy workflows", text)
        self.assertIn("Rebuild the three ordinary entrances in Tauri + React", text)
        self.assertIn("next click, source state, missing evidence", text)
        self.assertIn("### Phase 5: Audit-gated workflow migration", text)
        self.assertIn("searched-symbol -> `生成 3.0 量化推演`", text)
        self.assertIn("Move detailed engineering contract tables", text)
        self.assertIn("Keep margin ETF, trading discipline, backtest labs", text)
        self.assertIn("Do not remove Streamlit fallback/admin/debug during this stage", text)
        self.assertIn(
            "Do not remove the legacy workbench rollback path, but do not promote it as an ordinary 3.0 entrance",
            text,
        )
        self.assertIn("`LEGACY-DEBUG`", text)
        self.assertIn("Do not bypass DeepSeek, Tushare, AkShare, Supabase, or backtest governance", text)
        self.assertIn("safe params, ledgers, redaction, and no-trade/no-action boundaries", text)
        self.assertIn("Do not bypass service contracts, task governance, ledgers, redaction, or mode gates", text)
        self.assertIn("explicit POST task / worker / local fallback boundaries", text)
        self.assertIn("Do not treat docs/config/scaffold/preflight/local receipt, matrix, mock, or sanitizer evidence as production acceptance evidence", text)
        self.assertIn("Do not add broad LTG contracts, receipts, runbooks, or stage-scope manifests unless they directly reduce a current release blocker", text)
        self.assertIn("direct acceptance, safety scans, and no-trade/no-action review", text)
        self.assertIn("Fix push gate / CI evidence", text)
        self.assertIn("local gate or checkpoint evidence is not a substitute", text)
        self.assertIn("current matching remote CI green result or reviewed failure logs", text)
        self.assertIn("Keep the Legacy Bug / UX Audit current", text)
        self.assertIn("Rebuild LTG-13 Candidate Radar as a user-usable workflow", text)
        self.assertIn("searched-symbol -> `生成 3.0 量化推演`", text)
        self.assertIn("Show provider/model/cache/pending state clearly on the page", text)
        self.assertIn("Move excessive engineering audit tables", text)
        self.assertIn("away from ordinary user flow and into Settings / Developer / Audit", text)
        self.assertIn("ordinary pages should keep only user-facing summary", text)
        self.assertIn("missing-evidence, blocked/degraded, last-cache/result, and next-action rows", text)
        self.assertIn("unless an engineering detail directly explains the current decision surface", text)
        self.assertIn("Settings / Developer / Audit", text)

        for stale_phase_rule in (
            "Continue to prevent automatic heavy task execution",
            "Keep all heavy tasks button gated",
            "Require explicit user action for DeepSeek calls",
            "Require explicit user action for Tushare full scans and other heavy market scans",
            "Preserve the current business chain and existing legacy workbench while new surfaces mature",
            "preserve all current business flows",
            "Do not change DeepSeek, Tushare, AkShare, Supabase, or backtest business logic",
            "Do not change service contracts",
            "Do not change DeepSeek call logic",
            "Do not change Tushare, AkShare, or Supabase data chains",
            "Do not change the backtest engine",
            "### Phase 5: Gradual module migration",
            "- Migrate margin ETF.",
            "- Migrate trading discipline.",
            "- Migrate quant inference.",
            "Commit the current strategy execution card patch",
            "Add `docs/app_migration_plan.md`",
            "harden `desktop_app.py` startup self-checks",
            "extract the command center adapter from `app.py`",
            "Start a Tauri / React pilot only after the packet and local API boundary is stable",
            "The Streamlit app remains the primary runtime surface",
            "Short term: continue with pywebview + Streamlit polish",
            "### Option A: Continue pywebview + Streamlit polish",
            "This option keeps the current architecture",
            "Fit: best short-term path",
            "Code reuse rate: very high. Existing Streamlit pages",
            "Current feature stability: highest",
            "Keep the trading decision loop clear: refresh data, generate strategy execution advice, generate daily decision",
            "starting only with 综合推演中心 2.0",
            "presents the main trading workflow through packetized service outputs",
            "Default directly into 综合推演中心 2.0",
        ):
            self.assertNotIn(stale_phase_rule, text)

    def test_architecture_records_user_first_react_tauri_migration_boundary(self):
        root = Path(__file__).resolve().parents[1]
        text = (root / "docs" / "command_center_3_architecture.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("架构迁移不是把 Streamlit UI、旧导航、已知 bug 或历史 patchwork 一比一搬到 React/Tauri", text)
        self.assertIn("React route 层的普通用户中心应优先围绕", text)
        self.assertIn("今日作战台 / Daily Command Center", text)
        self.assertIn("股票量化推演 / Stock Quant Projection", text)
        self.assertIn("下一票雷达 / Candidate Radar", text)
        self.assertIn("重组服务 packets、数据源、信号、证据链和研究流程", text)
        self.assertIn("next click、Tushare/cache/DeepSeek/pending source", text)
        self.assertIn("research-only not-buy/sell boundary", text)
        self.assertIn("blocked/degraded state 和 last successful cache/result", text)
        self.assertIn("known bug、difficult-to-use UX、confusing workflow 或 unclear data lineage", text)
        self.assertIn("必须保持 `REDESIGN`、`LEGACY-DEBUG` 或 `RETIRE`", text)
        self.assertIn("直到有直接 UX/bug evidence 证明它可以进入普通 workflow", text)
        self.assertIn("工程合同、receipt、runbook 和 LTG audit 默认进入 Settings / Developer / Audit", text)

    def test_handoff_protocol_requires_migration_checkpoint_answers(self):
        root = Path(__file__).resolve().parents[1]
        text = (root / "docs" / "codex_handoff_protocol.md").read_text(encoding="utf-8")

        self.assertIn("Migration checkpoint answers", text)
        for question_fragment in (
            "What user capability was preserved",
            "What legacy UX problem was removed",
            "Which legacy bug or patchwork path was intentionally not migrated",
            "What became simpler for a non-technical user",
            "Which real blocker was reduced",
        ):
            self.assertIn(question_fragment, text)

        self.assertIn("Production-evidence boundary", text)
        self.assertIn("docs/config/scaffold/preflight/local receipt evidence", text)
        self.assertIn("real production acceptance evidence", text)
        self.assertIn("Legacy audit promotion gate", text)
        self.assertIn("whether any module was promoted to `KEEP`", text)
        self.assertIn("direct Legacy Bug / UX Audit evidence", text)
        self.assertIn("observed user action/workflow problem", text)
        self.assertIn("removed legacy bug/confusing UX/patchwork path", text)
        self.assertIn("data-lineage check", text)
        self.assertIn("replacement ordinary entrance", text)
        self.assertIn("frozen legacy path", text)
        self.assertIn("at most one main target and one supporting target", text)
        self.assertIn("modify no more than five files", text)
        self.assertIn("end with a `Checkpoint`", text)
        self.assertIn("Cycle scope", text)
        self.assertIn("main target, supporting target, changed file count", text)
        self.assertIn("one-main / one-support / five-file cap", text)
        self.assertIn("checkpoint-style cycle reporting", text)
        self.assertIn("either commit or checkpoint according to scope", text)
        self.assertIn("Checkpoint-only docs/config/runtime-mode wording cycles", text)
        self.assertIn("without forcing a commit unless the user explicitly asks for one", text)
        self.assertIn("explicit no-commit checkpoint status", text)
        self.assertIn("User pastes the returned report to ChatGPT", text)
        self.assertNotIn("User pastes CHATGPT_HANDOFF to ChatGPT", text)
        self.assertIn("Legacy parity means preserving useful user capabilities", text)
        self.assertIn("data sources, signals, evidence chains, and research workflows", text)
        self.assertIn("does not mean copying legacy UI, navigation, bugs, historical patchwork", text)
        self.assertIn("Before any legacy Streamlit workflow is promoted", text)
        self.assertIn("Legacy Bug / UX Audit classification", text)
        self.assertIn("`KEEP`, `REDESIGN`, `LEGACY-DEBUG`, or `RETIRE`", text)
        self.assertIn("known bugs, confusing UX, historical patchwork, or unclear data lineage", text)
        self.assertIn("out of ordinary workflow code", text)
        self.assertIn("Streamlit stays fallback / legacy / admin / debug", text)
        self.assertIn("React/Tauri ordinary entrances are demonstrably easier", text)
        self.assertIn("do not describe Streamlit as the primary 3.0 runtime surface", text)
        self.assertIn("Do not add broad LTG contracts, receipts, runbooks, or stage-scope manifests", text)
        self.assertIn("names the current release blocker they directly reduce", text)
        self.assertIn("must not claim an LTG is complete", text)
        self.assertIn("only direct acceptance evidence can support an LTG closeout claim", text)
        self.assertIn("Runtime-mode boundary", text)
        self.assertIn("cache_only", text)
        self.assertIn("manual", text)
        self.assertIn("live_light", text)
        self.assertIn("GET/cache/render/startup/search typing stayed silent", text)
        self.assertIn("Runtime policy row boundary", text)
        self.assertIn("`runtime_mode_policy_rows` still expose `cache_get_rule`", text)
        self.assertIn("`react_render_rule`", text)
        self.assertIn("`ledger_rule`", text)
        self.assertIn("`ordinary_entrance_visibility_rule`", text)
        self.assertIn("`production_evidence_rule`", text)
        self.assertIn("frontend-visible, non-editable, no-writeback, no-secret, and non-production evidence", text)
        self.assertIn("Ordinary task-boundary visibility", text)
        self.assertIn("`任务边界` remains in the user summary before Settings / Developer / Audit details", text)
        self.assertIn("`GET cache` / React render stayed read-only", text)
        self.assertIn("`manual` or `live_light`补证 path still goes through `POST task` / worker / local fallback", text)
        self.assertIn("Ordinary source-state chips", text)
        self.assertIn("`cache`, `Tushare`, `DeepSeek`, `pending`, `degraded`, and `last_successful_cache/result` remain visible", text)
        self.assertIn("read-only UI guidance", text)
        self.assertIn("did not create tasks, call provider/model, write cache/config, or promote production evidence", text)
        self.assertIn("Ordinary next-click rule", text)
        self.assertIn("what the one primary safe next click is", text)
        self.assertIn("disabled/degraded reasons are visible", text)
        self.assertIn("work-creating click still goes through POST task / worker / local fallback", text)
        self.assertIn("task status and no-trade/no-action boundaries", text)
        self.assertIn("Priority alignment", text)
        self.assertIn("push gate / CI", text)
        self.assertIn("Legacy Bug / UX Audit", text)
        self.assertIn("Candidate Radar", text)
        self.assertIn("searched-symbol -> `生成 3.0 量化推演`", text)
        self.assertIn("provider/model/cache/pending state", text)
        self.assertIn("engineering-audit demotion", text)
        self.assertIn("Ordinary-entrance state", text)
        self.assertIn("Daily Command Center", text)
        self.assertIn("Stock Quant Projection", text)
        self.assertIn("next click, Tushare/cache/DeepSeek/pending source", text)
        self.assertIn("missing evidence, research-only not-buy/sell boundary", text)
        self.assertIn("blocked/degraded state, and last successful cache/result", text)
        architecture = (root / "docs" / "command_center_3_architecture.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("`股票量化推演 / Stock Quant Projection` 可以读取 `GET /api/bootstrap/status` 作为只读 runtime-mode banner", architecture)
        self.assertIn("把 `cache_only/manual/live_light/live_full` 当前口径放在普通用户摘要里", architecture)
        self.assertIn("这不是 bootstrap launcher", architecture)
        self.assertIn("不创建 `POST /api/bootstrap/live-startup`", architecture)
        self.assertIn("不调用 provider/model，不写配置或 cache，不暴露 token/key", architecture)
        self.assertIn("不能当成 production evidence 或完整 `live_light` 实现", architecture)
        self.assertIn("legacy signal/capability parity 未完成边界", architecture)
        self.assertIn("不复制 Streamlit 图表 UI 或旧 tab navigation", architecture)
        self.assertIn("legacy signal/capability parity、browser visual QA", architecture)
        self.assertIn("legacy signal/capability parity 和 production replacement 继续标为 pending", architecture)
        self.assertIn("不把旧 Streamlit 图表 UI/tab 复制作为验收目标", architecture)
        self.assertIn("不证明 legacy signal/capability parity 或生产替代完成，不代表复制旧 Streamlit 图表 UI", architecture)
        self.assertIn("不证明 legacy signal/capability parity、durable CI evidence 或 production ECharts replacement", architecture)
        self.assertIn("经 Legacy Bug / UX Audit 判定应保留的能力、信号组和证据链", architecture)
        self.assertIn("不复制 Streamlit 页面 UI、tab navigation、已知 bug 或历史 patchwork", architecture)
        self.assertIn(
            "React/Tauri 普通入口更简单、更清晰、更可靠且 fallback-retirement evidence 通过",
            architecture,
        )
        self.assertNotIn("把 Streamlit 页面逐块迁移到 React/ECharts", architecture)
        self.assertNotIn("browser QA、performance trace、Streamlit parity 和 production replacement", architecture)
        self.assertNotIn("不证明 Streamlit parity 或生产替代完成", architecture)
        self.assertNotIn("不证明 Streamlit parity、durable CI evidence", architecture)

    def test_push_gate_guard_covers_commit_checkpoint_surfaces(self):
        root = Path(__file__).resolve().parents[1]
        push_gate = (root / "scripts" / "push_gate_3_0.sh").read_text(encoding="utf-8")
        ci_workflow = (
            root / ".github" / "workflows" / "command-center-3-push-gate.yml"
        ).read_text(encoding="utf-8")
        legacy_service = (root / "server" / "services" / "legacy_service.py").read_text(
            encoding="utf-8"
        )
        legacy_page = (root / "desktop" / "src" / "routes" / "LegacyTools.tsx").read_text(
            encoding="utf-8"
        )

        self.assertIn("Migration principle docs guard", push_gate)
        self.assertIn("tests.test_command_center_migration_principles", push_gate)
        self.assertIn("scripts/push_gate_3_0.sh mirrors", ci_workflow)
        self.assertIn("-m unittest tests.test_command_center_migration_principles", ci_workflow)
        self.assertIn("scripts/bootstrap_runtime_contract.py", ci_workflow)
        self.assertIn("runtime_mode_policy_rows config boundary fields", ci_workflow)
        self.assertIn("scripts/push_gate_3_0.sh", ci_workflow)
        self.assertIn("Bootstrap runtime contract", push_gate)
        self.assertIn("scripts/bootstrap_runtime_contract.py", push_gate)
        self.assertIn("local_gate_pass_is_not_remote_ci: true", push_gate)
        self.assertIn("remote_actions_status_known: false", push_gate)
        self.assertIn("latest_remote_run_verified_green: false", push_gate)
        self.assertIn("Local gate pass is not remote CI evidence", push_gate)
        self.assertIn("remote_ci_status_note", push_gate)
        self.assertIn("inspect matching remote Actions run before release", push_gate)

        for question_key in (
            "what_user_capability_was_preserved",
            "what_legacy_ux_problem_was_removed",
            "what_legacy_bug_or_patchwork_path_was_not_migrated",
            "what_became_simpler_for_nontechnical_user",
            "which_real_blocker_was_reduced",
        ):
            self.assertIn(question_key, legacy_service)

        self.assertIn("commit_questions", legacy_service)
        self.assertIn("migrationCommitQuestionRows", legacy_page)
        self.assertIn("迁移 commit checkpoint", legacy_page)
        self.assertIn("required_for_future_migration_commit", legacy_page)
        self.assertIn("不是 production evidence", legacy_page)
        self.assertLess(
            legacy_page.index("普通入口 UX 审计"),
            legacy_page.index("迁移 commit checkpoint"),
        )
        self.assertLess(
            legacy_page.index("迁移 commit checkpoint"),
            legacy_page.index("Legacy 模块 UX/bug 分类"),
        )


if __name__ == "__main__":
    unittest.main()
