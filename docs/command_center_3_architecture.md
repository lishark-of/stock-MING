# Command Center 3.0 Architecture

## 目标

Command Center 3.0 把正式主应用从 Streamlit 单体迁移到桌面 + API + 任务 + 存储的分层架构：

```text
Tauri desktop shell
→ React / Vite / TypeScript UI
→ FastAPI packet and task API
→ Celery + Redis / local fallback task runner
→ APScheduler scheduled task skeleton
→ DuckDB / Parquet / SQLite / Redis storage
→ existing Python quant and packet modules
```

Streamlit `app.py` 保留，但定位调整为 legacy/admin/debug，不再作为正式主入口；页面顶部已显示 Command Center 3.0 正式入口和 legacy/admin/debug 边界提示，并声明旧入口启动不创建任务、不自动外联、不改写 `strategy action`。`GET /api/legacy/cache` 现在输出 `primary_workflow_exit_audit`、`primary_workflow_exit_rows` 和 `primary_workflow_route_rows`，用本地 route inventory 审计普通主流程迁移覆盖；它还输出 `streamlit_fallback_dependency_contract` 和 `streamlit_fallback_dependency_rows`，把 Command Center 3 primary-ready route、ordinary-flow partial fallback dependency、legacy/admin/debug retained dependency、移除条件和 no feature cut 边界分开展示。当前正确状态是 `ordinary_workflow_exit_partial_fallback_required` / `streamlit_fallback_dependencies_visible_retirement_pending`，不能把它误称为 Streamlit 已完全退场。

## 迁移进度基线

后续规划以这张基线为准，不在每轮重新估算方向：

长期未完成项、优先级和验收标准集中维护在
[`docs/command_center_3_long_term_goals.md`](command_center_3_long_term_goals.md)。
架构文档描述当前系统形态；长期目标文档描述后续生产化路线。

| 模块 | 当前程度 |
|---|---:|
| Streamlit 保留为 legacy | 70% |
| FastAPI 后端骨架 | 60% |
| FastAPI 真实 cache API | 40%-50% |
| React/Vite 前端骨架 | 60% |
| React 页面可用化 | 30%-40% |
| Tauri 桌面壳 | 20% |
| Worker / Task 系统 | 35%-45% |
| Storage 层 | 40% |
| Factor Quant Hub 3.0 化 | 50% |
| ECharts 次日图谱 | 30%-40% |
| 完全替代 Streamlit 主流程 | 20%-30% |

## 为什么迁移

- Streamlit 的全局 rerun 容易让路由、按钮状态和重计算纠缠在一起。
- Tushare、DeepSeek、因子计算、回测等重任务需要从 UI 请求线程剥离。
- React 前端可以局部更新状态，不因为一个按钮导致整页重载。
- FastAPI 给现有 packet 合同提供稳定 API 边界。
- DuckDB/Parquet/SQLite/Redis 让大数据、元数据和热点缓存各归其位。

## 当前 MVP 已落地

### FastAPI

启动：

```bash
python3 -m uvicorn server.main:app --reload --port 8710
```

已提供：

- `GET /health`
- `GET /api/migration/status`
- `GET /api/packets`
- `GET /api/packets/{packet_key}`
- `GET /api/model-strategy/cache`
- `GET /api/next-session/cache`
- `POST /api/next-session/generate`
- `GET /api/factor-quant/cache`
- `POST /api/factor-quant/refresh-data`
- `POST /api/factor-quant/run-light`
- `POST /api/factor-quant/universe-research-plan`
- `POST /api/factor-quant/deepseek-explain`
- `GET /api/chokepoint/cache`
- `POST /api/chokepoint/run`
- `GET /api/serenity/cache`
- `POST /api/serenity/github-probe`
- `GET /api/storage`
- `GET /api/storage/catalog`
- `GET /api/storage/factor-values`
- `GET /api/storage/{dataset}`，当前白名单为 `factor_values`、`daily`、`daily_basic`、`moneyflow`、`trade_cal`、`backtest_results`
- `POST /api/storage/artifact-hygiene/dry-run`
- `POST /api/storage/schema-validation/dry-run`
- `POST /api/storage/partition-migration/dry-run`
- `POST /api/storage/compaction/dry-run`
- `POST /api/storage/cache-ttl/dry-run`
- `GET /api/tasks/catalog`
- `GET /api/tasks/{task_id}`

规则：

- `GET .../cache` 不触发 Tushare、DeepSeek、GitHub。
- `/health` 返回启动安全摘要；`GET /api/model-strategy/cache` 返回当前 DeepSeek 模型策略、用途映射和配置来源。二者都不包含 token/key，不触发模型调用。
- `/api/migration/status` 返回用户给定的 3.0 长期迁移进度基线、目标技术栈和安全原则；该接口只读、不外联、不重新估算进度。
- `/api/tasks/catalog` 返回按钮门控任务目录、可能外部源、call ledger 要求和交易边界；DeepSeek-capable 任务会声明 `deepseek_model_strategy_purpose`、配置键和非硬编码模型来源；该接口只读，不创建任务。
- `GET .../cache` 优先读取 `.stock_ming_3/meta.sqlite` 中已有持久化 packet；没有持久化 packet 时再读取 `.stock_ming_cache/command_center_latest.json` 本地快照或本地 builder；没有精确 packet 时返回 `cache_missing`，不会把旧 packet 冒充新 packet。
- `/api/packets/{packet_key}` 的读取优先级为 `sqlite_meta > snapshot > local_builder > missing`，并支持部分 2.0 本地快照别名，例如 `command_center_moneyflow_packet` → `moneyflow_packet`、`strategy_execution_packet` → `strategy_packet`。
- `POST` 默认返回 local fallback task，不在请求线程跑重计算；任务可通过 `/api/tasks/{task_id}` 轮询，记录 `pending → running → success` 状态历史、`progress`、`current_step`、`error_message_safe`、`output_packet_key` 和 `call_ledger`。DeepSeek-capable stub 和 guarded explanation task 会把集中模型策略引用写入 `call_ledger.request_params_safe`，但不会调用模型。
- 提交纪律保持为人工确认：不使用 `git add .`，不 push，除非用户明确确认。
- `/api/tasks` 返回 `command_center_3_task_status_index`，包含任务列表、状态计数、最新任务、`call_ledger_count` 和外部/交易边界汇总，供 3.0 前端状态面板与审计页展示。
- `/api/risk/cache` 输出 `trade_isolation_audit`、`trade_isolation_rows` 和 `trade_isolation_boundary_rows`，把风险 cache policy、task catalog 全量 POST route coverage、task/lifecycle no-trade/no-action flags、以及风险页/任务目录/packet registry 的前端边界可见性列成结构化审计。该审计只读本地 task catalog 和前端源码，不创建任务、不调用外部 provider、不接入券商或订单接口；未来真实交易集成必须另立项目、审批和安全设计。
- `/api/audit/cache` 同时输出 `release_gate_readiness_audit`、`release_gate_readiness_rows` 和 `.github/workflows` 本地静态清单，用来审计 `scripts/push_gate_3_0.sh` 是否包含 Python unittest、desktop build、3.0 smoke、diff check、secret scan、structured keyword review、artifact scan、可选 report、clean worktree、no push/no add dot/no external/no trade 边界。`scripts/secret_keyword_review_contract.py` 将普通 keyword 命中分类为结构化计数并抑制原始源码行输出；高风险 secret-like value 仍由 gate 阻断。`.github/workflows/command-center-3-push-gate.yml` 现在静态镜像该本地 gate：CI 创建 `.venv`、安装 desktop dependencies，并以 `PYTHON_BIN=.venv/bin/python` 运行脚本。该审计只读本地脚本和 workflow，不运行 gate、不调用 GitHub API；`local_gate_ready=true` 与 `ci_mirror_ready=true` 不是远端 check 结果，`false_positive_allowlist_review_pending` 仍保留为长期缺口。
- `POST /api/next-session/generate` 已从纯 stub 升级为本地 cache pipeline：读取已有 `command_center_next_session_projection_packet` cache，发现精确 packet 时写入 `.stock_ming_3/meta.sqlite`；没有精确 packet 时返回 `cache_missing` 任务结果且不写入假 packet。不调用 Tushare、DeepSeek、GitHub，不修改 `strategy action` 或 `operation_zones`。
- `POST /api/factor-quant/run-light` 已接入本地 light-mode pipeline：读取 `.stock_ming_cache/command_center_latest.json`，调用现有 Factor Quant Hub builder，写入 `.stock_ming_3/meta.sqlite`，并把 `runtime.factor_values` 同步写入 `.stock_ming_3/parquet/factor_values.parquet`；不调用 Tushare、DeepSeek、GitHub，也不修改 `strategy action`。
- Factor Quant Hub freshness gate 已支持 A 股交易日历语义：优先使用本地 `trade_cal` cache 推导 `expected_data_date`、`market_phase` 与 `trading_day_lag`；没有交易日历时退回工作日近似并标记 `calendar_validated=false`。过期、陈旧或盘中不可得数据只可审计展示，不进入 `composite_score`、强 support 或 `next_session_bridge.preview`。
- `GET /api/data-health/cache` 现在同时输出 LTG-01 freshness 验收矩阵、synthetic 长窗口样本验收、本地 `trade_cal` Parquet 物理验收和 `current_evidence_freshness_qa_contract`。矩阵把盘前、盘中、收盘集合竞价、16:30 后、周末/节假日、`trade_cal` 缺失、provider delay grace 与 stale/expired/historical/unknown 的 expected trade date、research-only 边界和 action 隔离写成可审计表格；current-evidence QA 进一步固定 expected trade date、data date 对齐、freshness state eligibility、历史样本隔离、provider-backed acceptance pending 和 decision-surface isolation。synthetic sample 使用实际 freshness gate 覆盖长窗口、节假日簇、长周末和缺今日行；local physical validation 只读已有 storage/DuckDB cache，检查 schema、日期窗口、开闭市行、当前日期覆盖、latest completed trading day 与 freshness gate context。它们都不调用 Tushare/DeepSeek/GitHub；缺失或覆盖不足时只输出 blocker，不刷新 provider、不写文件、不修改 `strategy action`。
- `GET /api/candidate-radar/cache`、`POST /api/candidate-radar/scan-quick`、`POST /api/candidate-radar/full-pool-plan` 与 `POST /api/candidate-radar/deep-scan-plan` 输出下一票雷达 coverage detail、scan acceptance、fast-scan runtime budget、fast-scan readiness 和 no-feature-loss acceptance：`coverage_detail_summary`、`scan_execution_summary`、`scan_acceptance_rows`、`fast_scan_runtime_budget_contract`、`fast_scan_runtime_budget_rows`、`fast_scan_readiness_audit`、`fast_scan_readiness_rows`、`no_feature_loss_acceptance_contract`、`no_feature_loss_acceptance_rows`、`provider_coverage_rows` 和 `degraded_mode_rows` 会把 universe size、provider blocked、stale input、missing provider data、freshness、local pool、候选展示上限、截断数量、worker 边界、last-cache fallback、full-pool boundary、deep-scan boundary、浏览器性能 trace 缺口、provider-backed acceptance 缺口与 degraded modes 结构化展示。full-pool plan 只写 `full_pool_scan_plan`、stage/filter/required-signal/blocker rows，不扫描全市场、不刷新 provider、不生成买入候选；deep-scan plan 只写 `deep_scan_plan`、stage/parity/required-signal/blocker rows，用来审计旧雷达功能覆盖和不降能缺口，不执行 deep_scan、不调用 DeepSeek、不刷新 provider。该层只读本地 snapshot/payload，不在页面渲染时补数、不做 full-pool/deep scan、不调用 Tushare/DeepSeek/GitHub、不把候选分数写入 `strategy action`；`fast_scan_runtime_budget_ready` 是本地静态预算合同，不等于浏览器性能 trace；`fast_scan_local_ready_full_pool_pending` 和 `no_feature_loss_acceptance_local_ready_production_pending` 都不等于生产雷达替代完成。
- `POST /api/tasks/refresh-tushare-facts` 已具备扩展接口验证矩阵、acceptance audit、failure-mode QA 和 request-parameter QA：默认只刷新 `daily/daily_basic/moneyflow`，按钮 payload 可选择 `trade_cal`、两融、涨跌停、筹码、公告/预告、股东增减持、限售解禁、质押等接口；每个接口会进入 `api_validation_rows`、`api_acceptance_audit`、`failure_mode_qa_contract`、`request_parameter_qa_contract`、`provider_acceptance_readiness_audit` 与 `call_ledger`。当前 `daily/daily_basic/moneyflow/trade_cal` 启用 Parquet 落盘，其他扩展接口以 `parquet_status=not_enabled` 审计展示。`api_acceptance_audit` 只验证 call-ledger 字段、安全终态、错误清洗、未选接口不误标 verified 和非 Parquet 接口不假写入；`failure_mode_qa_contract` 只分类已有 call-ledger 的 empty/no-record、permission denied、parse/invalid-result、missing required parameter、provider error 和 matrix-only 状态，不发起 provider 调用；`request_parameter_qa_contract` 只审计安全参数、`ts_code` 预检阻断、日期上下文字段、alias handling 和 matrix-only 边界，不验证真实 provider 窗口；`provider_acceptance_readiness_audit` 汇总全接口生产验收阻断项，保持 `provider_acceptance_pending`、`provider_backed_acceptance_done=false` 和 `production_tushare_pipeline_complete=false`，直到真实 provider-backed 全接口样本和 target group 验收被显式证明。
- `GET /api/next-session/cache` 已输出 ECharts 成熟版只读合同：`chart_payload` 除历史 close、参考线、操作区和三情景路径外，还包含数据可信度、持仓冲突、DeepSeek 状态、latest close 锚定校验、参考线来源、操作区点击说明、`interaction_readiness_audit` 和 `interaction_readiness_rows`。React/ECharts 只渲染这些后端 cache 字段，不计算交易动作、不改价格/持仓、不改 `operation_zones`；交互审计明确区分 ready/blocker/pending，并保留 Streamlit parity 未完成边界。
- React 已加入受控动效清晰度层：route/card/metric/task 使用 CSS 有限时长动效，导航 active route 通过 `aria-current`、`data-route-active` 和一次性 context sweep 明确当前位置，状态徽标通过 `data-status-tone` 与小圆点强化状态可见性，`StateClarityRail` 将 cache/page state、task receipt、task status 与 Candidate radar 状态显示为 accepted/running/blocked/done 等视觉边界。cache loading/error/empty、task phase panel 和 task receipt 还共享 `state_change_confirmation` / `cc-phase-confirm` 有限确认线索，让刷新和任务状态变化更容易看见。`scripts/motion_viewport_qa_contract.py` 固定 LTG-14 的 route/viewport QA 矩阵并接入 push gate，但它只做本地静态合同，不运行浏览器。Next-session ECharts 使用短时更新动效并尊重 `prefers-reduced-motion`，Candidate radar primary result cluster 只基于已有 cache 状态做视觉分组。`/api/audit/cache` 还输出 `motion_clarity_audit`、`motion_clarity_rows`、`motion_production_qa_contract` 和 `motion_production_qa_rows`，静态审计 motion tokens、finite keyframes、navigation/status context cues、task/cache phase confirmation cues、motion viewport QA contract、reduced-motion fallback、chart/radar clarity scopes、layout containment、no timer/RAF loop、provider-call 边界，以及生产动效所需的视觉 QA / 性能 trace pending 状态。该层不使用定时器或 `requestAnimationFrame`，不触发外部调用、不重新计算候选/图谱、不修改 packet、价格、持仓、`operation_zones` 或 `strategy action`；`static_ready` 和 `local_motion_qa_ready` 都不等于浏览器视觉验收完成或生产动效完成。
- Factor Test Lab 已从空 schema 进入 light research metrics：`command_center_factor_test_packet` 可对本地小样本 observations 计算 IC、Rank IC、ICIR、Top-Bottom 分组收益、换手、成本后收益、最大回撤，并输出 `quality_summary`、必需指标缺口、样本窗口摘要和 `research_pass/watchlist/disabled/invalid/not_enough_data` 状态验收合同。packet 还会输出 `small_pool_acceptance`，逐项审计本地 light observations 是否具备 IC/Rank IC/ICIR、分组收益、成本、回撤、中性 IC、样本外/衰减和 PIT/lookahead/survivorship 检查；它不把 storage query rows 当指标样本，也不代表真实小股票池或全市场生产验收。新增的 `production_validation_qa_contract` 固定后续生产验证清单：provider-backed small pool、多周期 forward returns、rolling IC/ICIR、样本外/衰减、生产成本假设、中性稳定性、PIT/lookahead/survivorship、storage-query 边界、研究状态隔离和 trade/action 隔离；它不运行 provider-backed 样本或 full-market 研究。GET factor cache 还会附加 `factor_values` DuckDB 查询消费合同，展示 typed projection、`duckdb_query_result_contract.v1`、cursor `page_info` 和本地查询血缘；它只证明 Factor Test Lab 已可消费 storage query contract，不把 query rows 当作生产 IC 验收。Factor universe 也输出 `current_target/watchlist/custom_pool/full_pool` 研究合同；`POST /api/factor-quant/universe-research-plan` 已提供按钮门控的本地读取计划任务，消费 `factor_values/daily/daily_basic/moneyflow/trade_cal` storage 查询合同并写回 `universe_research_task_plan`。Factor Quant Hub 同时暴露 `universe_execution_readiness_audit` 和 `universe_execution_readiness_rows`，把 read-plan、storage contract、worker batch、rank/zscore、中性化、full-pool 验收、frontend read-only、partial-pool 边界和交易隔离汇总到同一审计层；`read_plan_ready_execution_pending` 不等于 full-pool 因子研究完成。该能力仍是 research-only，不跑 full market，不把 partial pool 当 full-market proof，不进入 `strategy action`、`core_action`、`evidence_effects` 或 `next_session_projection`；`research_pass` 也不是买入信号。
- `POST /api/factor-quant/deepseek-explain` 已接入 guarded explanation pipeline：读取 Factor Quant Hub cache，准备未发送的安全 prompt 预览；如提供本地解释 payload，仅按六个白名单字段清洗并写回 SQLite cache，同时写入 `deepseek_validation_summary`、`input_hash`、`output_hash`、`parse_failed`、`model_call_status`。Factor Quant Hub cache 和按钮任务还会输出 `deepseek_json_stability_audit` / `deepseek_json_stability_rows`，本地审计 75% 历史小样本 JSON 成功率、>90% 目标线、response_format 强约束缺口、更大 benchmark 缺口、token 预算和默认关闭的 `auto_after_task`。当前阶段使用本地 sanitizer/prompt 合同验证 DeepSeek pro/flash 解释边界，不真实调用 DeepSeek、不覆盖数值、不修改 `strategy action`，也不把该审计当成生产自动解释完成。
- 任务生命周期已同步写入 SQLite metadata store；内存状态丢失后，`/api/tasks/{task_id}` 仍可从本地 SQLite fallback 读回任务状态。
- `/api/packets` 已暴露 SQLite packet/task metadata 摘要、packet source rows 和固定读取优先级，便于前端判断哪些 packet 来自持久化 cache。
- `/api/model-strategy/cache` 已独立暴露 DeepSeek 模型策略：`default/explain/projection/factor_explain` 默认走解释级模型，`fast/healthcheck/feeder` 默认走 fast 模型；模型名统一从 `DEEPSEEK_EXPLAIN_MODEL`、`DEEPSEEK_FAST_MODEL`、`DEEPSEEK_DEFAULT_MODEL` 或集中默认值读取，调用点、任务目录和任务回执不得硬编码。
- `GET /api/storage` 暴露 Parquet/DuckDB 的 `factor_values`、`daily`、`daily_basic`、`moneyflow`、`trade_cal`、`backtest_results` 只读状态和 dataset catalog；缺文件返回 `missing`，不触发 Tushare、回测或因子计算。
- `GET /api/storage` 与 `GET /api/storage/catalog` 暴露 DuckDB query service policy：canonical dataset path、支持的 `limit/cursor/ts_code/trade_date/start_date/end_date` 过滤、最大 limit、参数绑定、typed projection、offset cursor pagination 和前端不直接读 DataFrame 的边界。React Storage 的 cursor 控件和 dataset filters 只把 `page_info.next_cursor`、`limit`、`ts_code`、`trade_date`、`start_date`、`end_date` 传回 GET storage API，不刷新 provider、不写 Parquet、不直接读取 DataFrame；该策略只读、不执行刷新、不写 Parquet。
- `GET /api/storage` 与 `GET /api/storage/catalog` 暴露 `schema_migration_preflight`，只展示 canonical dataset 的目标 schema version、required columns、primary key、partition expectation 和 manual migration boundary；`physical_validation_done_count=0`、`migration_executed_count=0`，不读取 payload、不写 Parquet、不执行真实迁移。
- `GET /api/storage` 与 `GET /api/storage/catalog` 暴露 `dataset_version_policy`，只展示 declared dataset version、未来 manifest 路径、物理版本验证边界和 `manifest_written_on_get=false`；它不创建 manifest、不验证物理版本、不代表 dataset version migration 已完成。
- `GET /api/storage` 与 `GET /api/storage/catalog` 暴露 `storage_production_blocker_audit` 和 `storage_production_blocker_rows`，把 LTG-05 仍未完成的物理 schema validation、schema migration、dataset version manifest validation、partition migration、physical compaction、TTL refresh execution 和 DuckDB dependency 状态列成生产阻断项。`storage_production_blocked` 是当前正确状态；它不写文件、不刷新 provider、不把 dry-run/preflight 误称为 production。
- `POST /api/storage/schema-validation/dry-run` 读取本地 Parquet schema metadata，比较物理列与 schema contract，输出 `schema_validated` / `schema_mismatch` / `missing_dataset`，但不读取行 payload、不写 Parquet、不执行真实迁移。
- `POST /api/storage/partition-migration/dry-run` 结合 schema validation 与 partition contract 生成分区迁移计划，输出 ready/blocked/missing 行；不会读取行 payload、不会写 partitioned Parquet、不会执行真实迁移。
- `POST /api/storage/compaction/dry-run` 基于本地 Parquet metadata 和 size threshold 生成 compaction ready/not-needed/missing 行；不会读取行 payload、不会重写 Parquet、不会执行物理压缩。
- `POST /api/storage/cache-ttl/dry-run` 基于本地文件 metadata 生成 TTL fresh/stale/missing 与 refresh recommendation 清单；不会补数、不会调用 Tushare/DeepSeek/GitHub、不会写 Parquet，也不代表 provider refresh 已完成。
- `GET /api/storage/catalog` 独立暴露 dataset catalog，供前端、worker 和后续任务读取数据集用途、别名、写入边界和未来任务归属；该接口只读、不写 Parquet、不外联。
- `POST /api/factor-quant/refresh-data` 当前仍是安全 stub；真实 Tushare 刷新后续必须继续保持按钮门控和 call ledger。
- 所有响应使用统一 envelope：`ok/data/error/call_ledger/warnings`。

### DeepSeek 模型策略

DeepSeek 模型名不在调用点硬编码，统一从 `.streamlit/secrets.toml` 或环境变量读取：

```text
DEEPSEEK_EXPLAIN_MODEL=deepseek-v4-pro
DEEPSEEK_FAST_MODEL=deepseek-v4-flash
DEEPSEEK_DEFAULT_MODEL=deepseek-v4-pro
```

- `explain/projection/factor_explain`：优先使用 `DEEPSEEK_EXPLAIN_MODEL`，再退回 `DEEPSEEK_DEFAULT_MODEL`。
- `fast/feeder/healthcheck`：优先使用 `DEEPSEEK_FAST_MODEL`，再退回 `DEEPSEEK_DEFAULT_MODEL`。
- 未配置时使用安全默认策略：解释类走 pro，轻量/体检/feeder 类走 flash。
- 模型配置只记录模型名，不包含 token/key；是否调用 DeepSeek 仍由按钮门控或显式任务控制。
- `server/services/model_strategy_service.py` 提供统一模型策略引用 helper；task catalog、DeepSeek-capable local stub、Factor Quant Hub 的 guarded explanation task 都复用该 helper 写入审计字段。
- React 的 `ModelStrategy.tsx` 和 `TaskCatalog.tsx` 只读展示模型用途、配置键、非硬编码状态和 `contains_secret=false`；通用 `DataLineageTable` 会把嵌套 `call_ledger` / `request_params_safe` 以 JSON 形式展开，避免审计信息被显示成 `[object Object]`。

### Desktop

启动：

```bash
cd desktop
npm install
npm run dev
```

Tauri 开发：

```bash
scripts/check_tauri_env.sh
scripts/dev_server.sh
cd desktop
npm install
npm run tauri dev
```

`scripts/check_tauri_env.sh` 只做本地环境预检，不安装依赖、不启动 Tauri、不调用 Tushare/DeepSeek/GitHub、不读取 token/key。
`scripts/dev_server.sh` 默认使用项目 `.venv/bin/python` 启动 FastAPI；只有显式覆盖或本地 `.venv` 不可执行时才退回 `python3`。
如果本机未安装 Rust/Cargo，只运行 Vite 前端即可；Tauri dev mode 需要安装 Rust 后再执行 `npm run tauri dev`。
Tauri dev mode 还要求 `desktop/src-tauri/Cargo.lock` 与 `desktop/src-tauri/icons/icon.png` 存在；`desktop/src-tauri/target/` 与 `desktop/src-tauri/gen/` 为本地生成物，不提交。
当前 Tauri 开发模式不自动拉起 FastAPI：先运行 `scripts/dev_server.sh`，再运行 `cd desktop && npm run dev` 或 `cd desktop && npm run tauri dev`。`GET /api/desktop/preflight-cache` 会展示 `api_base_info`、`dev_launch_plan`、`production_launch_plan`、`production_runtime_contract`、`tauri_build_artifact`、`backend_offline_ux_contract`、`packaged_runtime_qa_contract` 和 `production_blocker_audit`，但不会执行这些命令、不会读取 token/key、不会调用 Tushare/DeepSeek/GitHub。`production_runtime_contract` 只声明手动 FastAPI 启动策略、`~/.stock_ming_3/desktop.local.json` 配置路径策略、`~/.stock_ming_3/logs/command_center_3.log` 日志路径策略和前端 secret 边界；它不读取配置值、不写日志、不启动后端、不验证 packaged runtime。React API client 在本地 FastAPI 不可达时会返回 `backend_offline_or_unreachable` 安全 envelope，并通过 `BackendOfflineNotice` 给出清晰离线状态；离线提示只显示去除查询串、hash、用户名和密码后的 API base。`backend_offline_ux_contract` 只做静态源码审计，不启动 FastAPI、不运行 Tauri、不等于 packaged runtime 离线验收。`packaged_runtime_qa_contract` 固定 release artifact、backend startup、packaged offline UX、config/log runtime path、macOS signing/notarization、startup no-external 和 secret bundle 的 QA 矩阵；它不打开 packaged app、不运行 `npm`/`cargo`、不读取配置值、不写日志。`tauri_build_artifact` 只读检测本地 `desktop/src-tauri/target/release/stock_ming_command_center` release binary，GET cache 不执行 `npm`、`cargo` 或 Tauri；检测到 release binary 不等于 sidecar/offline UX/signing/notarization 完成。`production_blocker_audit.status=production_package_blocked` 是当前正确状态：它要求未来显式验证 build artifact QA、后端启动/sidecar 策略、packaged-runtime 离线提示、配置/日志路径运行时行为以及 macOS 签名/公证流程后，才可声称 production desktop package 完成。

### Worker / Scheduler

Celery worker：

```bash
scripts/run_worker.sh
```

APScheduler：

```bash
scripts/run_scheduler.sh
```

默认不启用真实收盘后刷新。只有显式设置 `COMMAND_CENTER_ENABLE_SCHEDULED_REFRESH=1` 后才进入定时任务模式。
`GET /api/worker/cache` 会展示每类任务的 `dispatch_plan_rows`：未来 Celery queue、local fallback、Redis/Celery 前置条件、retry/cancel/lock/dedupe/task_log 要求和 scheduler 边界。它还会展示 `worker_production_blocker_audit`，把 Redis 包/配置、Celery 包/worker 启动、stub 任务迁移、队列合同、按钮门控、call_ledger 要求、scheduler 默认关闭、GET cache 不派发和本地控制面只读状态列成阻断审计。新增的 `worker_healthcheck_qa_contract` 是未来显式生产 worker healthcheck 的静态 QA 矩阵，覆盖 Celery 进程可见性、Redis broker 可达性、synthetic task round trip、跨进程 retry/cancel、scheduler 默认关闭、provider/model 不自动调度、task log persistence、外部调用边界和 secret redaction。该矩阵、blocker audit 和 healthcheck QA contract 都是只读合同，不执行 healthcheck、不派发任务、不 ping Redis、不启动 worker、不把 preflight 或 QA contract 误写为 production worker 完成。

### Storage

- SQLite：packet 元数据、任务状态、用户配置。当前已落地 packet payload、packet metadata 和 task lifecycle metadata。
- Parquet：daily、daily_basic、moneyflow、trade_cal、factor_values、backtest_results。当前已提供 `factor_values`、`daily`、`daily_basic`、`moneyflow`、`trade_cal`、`backtest_results` 文件状态接口和 dataset catalog，并由 light-mode 因子任务写入 `factor_values`。
- DuckDB：通过 FastAPI service 查询本地 Parquet。当前已提供 `factor_values`、`daily`、`daily_basic`、`moneyflow`、`trade_cal`、`backtest_results` 缺文件安全查询、`ts_code`/日期窗口过滤、typed projection、`duckdb_query_result_contract.v1`、offset cursor `page_info`、limit guard、参数绑定、只读 query service policy、React cursor 控件和 React dataset filters；React 只显示结果与策略，通过 FastAPI 传递 cursor/filter 参数，不直接读 DataFrame。
- Schema migration preflight：当前只做 metadata-only 预检，列出 schema version、required columns、primary key、partition expectation、当前 parquet 状态和人工迁移边界；不做物理列校验、不迁移、不重写数据集。
- Dataset version policy：当前只做 cache-only 版本策略矩阵，列出 declared dataset version、manifest 路径和物理验证状态；不写 `_dataset_versions.json`、不读取 payload、不把声明版本当成生产版本验收。
- Schema validation dry-run：按钮门控读取 Parquet schema metadata，比较实际列与 canonical contract；它可以证明某个本地文件当前 schema 是否匹配，但仍不是 production migration，也不会重写数据集。
- Partition migration dry-run：按钮门控生成目标 partitioned path、partition columns、ready/blocked/missing 状态；它不调用 partition writer，不创建分区目录，不代表真实 partition migration 完成。
- Compaction dry-run：按钮门控生成 compaction ready/not-needed/missing 清单；它不调用 compaction writer、不重写 Parquet、不代表真实 compaction 完成。
- Cache TTL dry-run：按钮门控生成 fresh/stale/missing 与 refresh-recommended 清单；它只读取本地文件状态，不执行 provider refresh、不写 Parquet、不读取行 payload、不代表数据新鲜度生产验收完成。
- Artifact hygiene：`GET /api/storage` 只读展示 `.stock_ming_3`、legacy cache、frontend build、Node dependencies、Tauri target 和 Python bytecode 的路径级边界；`POST /api/storage/artifact-hygiene/dry-run` 只生成本地清理预检任务和候选清单。两者都不会删除文件、读取 payload、扫描 secret 值、刷新外部服务或修改 `strategy action`。
- Redis：Celery broker、任务状态、热点 packet cache；未安装时可使用 memory fallback。

## 边界

- 不执行真实交易。
- 不自动下单。
- 不泄露 token/key。
- DeepSeek 只做解释整理，不作为数据源。
- Tushare、DeepSeek、GitHub 不在应用启动或 cache GET 时自动调用。
- 因子结果只进入 evidence_effects 预览，不修改 strategy action。
- Streamlit 仅作为 legacy/admin/debug 入口保留，普通主路径迁往 React/Vite/Tauri + FastAPI；Legacy 启动不创建任务、不自动调用外部源、不绕过 strategy guardrails。Legacy 页面展示的 `primary_workflow_exit_audit` 只做本地退出准备度审计，不打开 Streamlit、不运行旧工具、不移除 fallback；只有 route coverage 无 fallback blockers、迁移清单清空并且旧保护仍在时，才能进入完全退场。
- 现有 packet key 保持不变。
- 不使用 `git add .`；每个提交必须按文件或 hunk 精确 staging。
- 不 push，等待用户确认。

## 后续阶段

详细路线图见 [`docs/command_center_3_long_term_goals.md`](command_center_3_long_term_goals.md)。后续开发应围绕该文档中的 LTG-01 到 LTG-14 推进，并保持 cache/task/model/provider/trading 边界。

1. 继续扩大 SQLite/Redis 持久化 packet 覆盖面，逐步减少只能从本地快照读取的旧 packet。
2. 把 `refresh_factor_data` 等 local fallback task stub 迁移到 Celery worker，并保留相同任务状态合同。
3. 继续验收 `refresh_factor_data` 扩展接口，并把 margin、limit、cyq、hard risk 等结果逐步写入 DuckDB/Parquet。
4. 安装 Rust 后验证 Tauri dev mode；生产打包放到后续阶段。
5. 把 Streamlit 页面逐块迁移到 React/ECharts。
6. 最后将 Streamlit 仅保留为 legacy/admin/debug。
