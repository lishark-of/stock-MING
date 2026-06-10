# Command Center 3.0 Migration Map

| Streamlit/现有模块 | 当前文件 | 3.0 API | 3.0 前端页面 | 是否重计算 | 是否任务化 |
|---|---|---|---|---|---|
| 调用审计 / 外部边界 | `server/services/*_service.py`, `server/services/task_service.py` | `GET /api/audit/cache` | `CallLedgerAudit.tsx` | cache GET 聚合本地 cache API 与任务 `call_ledger`；不刷新、不外联 | 否；只读审计 |
| DeepSeek 模型策略 | `config.py`, `server/services/model_strategy_service.py` | `GET /api/model-strategy/cache` | `ModelStrategy.tsx` | cache GET 只读展示用途到模型映射、配置键名和安全边界；不调用模型、不读取凭据 | 否；真实解释仍需按钮任务 |
| 次日操作图谱 | `command_center_next_session_projection.py`, `app.py` | `GET /api/next-session/cache`, `POST /api/next-session/generate` | `NextSessionMap.tsx` | cache GET 不重算；没有精确新 packet 时返回 `cache_missing`；POST 只读本地 cache 并在有精确 packet 时写入 SQLite | 是，POST 已本地 cache pipeline |
| Factor Quant Hub | `command_center_factor_research.py`, `app.py` | `GET /api/factor-quant/cache`, `POST /api/factor-quant/refresh-data`, `POST /api/factor-quant/run-light` | `FactorQuantHub.tsx` | cache GET 读取本地快照/SQLite；run-light 本地 light 计算并写入 factor_values Parquet；refresh-data 后续接 Tushare | 是，run-light 已本地 pipeline |
| 市场环境 / 盘面证据 | `command_center_*_packet.py`, `app.py` | `GET /api/market/cache` | `MarketContext.tsx` | cache GET 只读展示市场状态、资金流、两融、涨跌停情绪、龙虎榜、筹码和 ETF 替代，不刷新行情 | 后续任务化；当前不提供 POST |
| 交易纪律 / 决策闭环 | `strategy_execution_service.py`, `command_center_decision_engine.py`, `app.py` | `GET /api/discipline/cache` | `DisciplineLoop.tsx` | cache GET 只读展示纪律 packet、决策闭环、今日动作和满血刷新步骤，不运行回测 | 后续任务化；当前不提供 POST |
| 策略执行 / 今日决策 | `strategy_execution_service.py`, `command_center_decision_engine.py`, `command_center_strategy_summary.py` | `GET /api/strategy/cache` | `StrategyTrace.tsx` | cache GET 只读展示 `strategy_execution_packet` / `command_center_decision_packet`，不生成新动作 | 后续任务化；当前不提供 POST |
| 持仓画像 / 标的上下文 | `command_center_home_snapshot.py`, `strategy_execution_service.py`, `app.py` | `GET /api/position/cache` | `PositionContext.tsx` | cache GET 只读展示 `holding_action`、风险预算和首页快照摘要，不刷新价格 | 否；后续可接按钮任务 |
| 下一票候选雷达 | `command_center_radar_packet.py`, `command_center_home_snapshot.py`, `app.py` | `GET /api/candidate-radar/cache` | `CandidateRadar.tsx` | cache GET 只读展示 `radar_packet` 与 `next_ticket_candidates`，不扫描全市场 | 后续任务化；当前不提供 POST |
| 风险护栏 / 安全线 | `command_center_home_snapshot.py`, `strategy_execution_service.py`, `app.py` | `GET /api/risk/cache` | `RiskGuardrails.tsx` | cache GET 只读展示 `risk_alerts`、`safety_line`、执行护栏、旧链状态和风险预算，不清除风险标记 | 后续任务化；当前不提供 POST |
| A 股事实血缘 | `command_center_evidence_summary.py`, `command_center_*_packet.py` | `GET /api/evidence/cache`, `/api/packets/{packet_key}` 与后续 fact refresh task | `AShareEvidenceRadar.tsx` | cache 不重算，支持本地快照别名 | 后续任务化 |
| 数据能力/数据源体检 | `command_center_data_capability_console.py`, `command_center_data_health_ledger.py`, `app.py` | `GET /api/data-capability/cache`，后续 provider refresh task | `DataCapabilityConsole.tsx` | cache GET 不检测；只读本地能力 packet | 后续任务化 |
| 数据健康时间线 / Provider 诊断 | `command_center_data_health_ledger.py`, `command_center_data_capability_console.py`, `app.py` | `GET /api/data-health/cache` | `DataHealthTimeline.tsx` | cache GET 只读健康时间线、provider 诊断、能力矩阵、恢复动作和缺口报告；不 ping provider、不刷新数据 | 后续 provider probe 任务化；当前不提供 POST |
| 数据恢复中心 | `command_center_data_capability_console.py`, `command_center_data_health_ledger.py`, `app.py` | `GET /api/recovery/cache` | `RecoveryCenter.tsx` | cache GET 只读展示恢复动作、恢复时间线、Provider 恢复矩阵和缺口报告，不执行恢复 | 后续任务化；当前不提供 POST |
| Tushare 数据刷新 | `tushare_adapter.py`, `app.py` | 后续 `refresh_tushare_facts` task | Factor / Next Session / Evidence / Data Capability pages | 是 | 是，当前 stub |
| 交易记录实验室 | `trade_review_log.py`, `app.py` | `GET /api/trade-review/cache` | `TradeReviewLab.tsx` | 否，cache-only 读取本地 `trade_review_log.jsonl` | 否 |
| 旧量化/回测 | `command_center_quant_packet.py`, `backtester.py` | `GET /api/quant/cache`，后续 `/api/backtest/run` | `QuantBacktestLab.tsx` | cache GET 不重算；后续 POST task 才可运行回测 | 后续任务化 |
| 产业链瓶颈扫描 | `command_center_analysis_methods.py`, `analysis_engine.py`, `app.py` | `GET /api/chokepoint/cache`, `POST /api/chokepoint/run` | `ChokepointScan.tsx` | cache GET 不外联；没有精确 packet 时只返回缺口和旧分析摘要 | 是，POST 当前 stub |
| Serenity 方法雷达 | `command_center_serenity_method_radar.py`, `app.py` | `GET /api/serenity/cache`, `POST /api/serenity/github-probe` | `SerenityMethodRadar.tsx` | cache 使用本地方法基线；probe 后续外联 | 是，POST 当前 stub |
| DeepSeek 解释器 | `analysis_engine.py`, `deepseek_safety.py`, `command_center_*` | `POST /api/factor-quant/deepseek-explain` 等 | 页面按钮 | 只解释已有结构化结果 | 是，当前 stub |
| Packet Registry | `command_center_packet_registry.py` | `GET /api/packets`, `GET /api/packets/{packet_key}` | `CommandCenterHome.tsx` | 否 | 否 |
| Storage datasets | `storage/parquet_store.py`, `storage/duckdb_store.py` | `GET /api/storage`, `GET /api/storage/catalog`, `GET /api/storage/{dataset}` | `CommandCenterHome.tsx` | 否，只读 Parquet/DuckDB 状态和数据集目录；白名单 `factor_values/daily/daily_basic/moneyflow/backtest_results` | 否 |
| Worker / Task runtime | `worker/celery_app.py`, `worker/tasks_*.py`, `worker/scheduler.py`, `server/services/task_service.py` | `GET /api/worker/cache`, `GET /api/tasks`, `POST /api/tasks/{task_id}/cancel` | `WorkerRuntime.tsx`, `TaskCatalog.tsx` | cache GET 不连接 Redis、不启动 Celery、不启动 APScheduler；取消任务只改本地状态 | 是，POST task / cancel 走 FastAPI lifecycle |
| Tauri desktop shell | `desktop/src-tauri/*`, `scripts/check_tauri_env.sh` | 连接本地 FastAPI `8710` | Tauri window / Vite dev | 否，预检不启动 Tauri | 否 |
| Streamlit 旧工作台 | `app.py`, `visual_components.py` | `GET /api/legacy/cache`；作为 legacy | `LegacyTools.tsx` | cache GET 只读展示旧工作台桥接、迁移清单、旧数据缺失账本，不运行旧工具 | 后续任务化；当前不提供 POST |

## 当前可用 API

- `/health`
- `/api/audit/cache`
- `/api/model-strategy/cache`
- `/api/packets`
- `/api/packets/{packet_key}`
- `/api/market/cache`
- `/api/discipline/cache`
- `/api/evidence/cache`
- `/api/data-capability/cache`
- `/api/data-health/cache`
- `/api/recovery/cache`
- `/api/next-session/cache`
- `/api/factor-quant/cache`
- `/api/serenity/cache`
- `/api/chokepoint/cache`
- `/api/storage`
- `/api/storage/catalog`
- `/api/storage/factor-values`
- `/api/storage/{dataset}`
- `/api/legacy/cache`
- `/api/strategy/cache`
- `/api/position/cache`
- `/api/candidate-radar/cache`
- `/api/risk/cache`
- `/api/trade-review/cache`
- `/api/quant/cache`
- `/api/tasks/{task_id}`
- `/api/tasks/{task_id}/cancel`
- `/api/tasks`
- `/api/worker/cache`

`GET` 类 cache API 当前已可读取 `.stock_ming_cache/command_center_latest.json` 中的本地快照或本地 builder 结果，不调用 Tushare、DeepSeek、GitHub。精确 packet 缺失时返回 `cache_missing`，并附带可审计的 legacy 快照摘要。

`/api/audit/cache` 已接入调用审计 / 外部边界只读迁移：聚合本地 cache API 返回包与任务状态中的 `call_ledger`、外部调用标志和交易边界；不调用 Tushare/DeepSeek/GitHub/Redis，不刷新数据，不运行回测，不执行真实交易，不修改 `strategy_execution_packet.action`。缺失 `call_ledger` 的本地项只作为审计提示，不代表自动外联。

`/api/model-strategy/cache` 已接入 DeepSeek 模型策略只读迁移：读取集中配置中的 `DEEPSEEK_EXPLAIN_MODEL`、`DEEPSEEK_FAST_MODEL`、`DEEPSEEK_DEFAULT_MODEL` 选择逻辑，输出用途到模型映射、配置键名、默认/覆盖状态和调用血缘；不调用 DeepSeek、不读取凭据、不调用 Tushare/GitHub、不执行真实交易、不修改 `strategy_execution_packet.action`。

`/api/worker/cache` 已接入 Worker / Task runtime 只读迁移：检查本地 `worker` scaffold、Celery/Redis/APScheduler 依赖可见性、task catalog 和 local fallback 状态；不连接 Redis、不启动 Celery worker、不启动 APScheduler、不调度真实 Tushare/DeepSeek/GitHub 任务、不执行真实交易、不修改 `strategy_execution_packet.action`。

`/api/market/cache` 已接入市场环境 / 盘面证据只读迁移：读取本地 `market_packet`、`market_profile_evidence`、`moneyflow_packet`、`margin_packet`、`dragon_tiger_packet`、`limit_emotion_packet`、`chip_packet`、`etf_packet` 和 `margin_etf_summary`，输出盘面状态、资金流、两融、龙虎榜、涨跌停情绪、筹码和 ETF 替代说明；不调用 Tushare/AkShare/yfinance/DeepSeek/GitHub、不刷新行情或资金流、不执行真实交易、不修改持仓或 `strategy_execution_packet.action`。

`/api/discipline/cache` 已接入交易纪律 / 决策闭环只读迁移：读取本地 `discipline_packet`、`decision_loop_status`、`today_action`、`decision_packet`、`strategy_packet`、`full_refresh_steps`、`home_data_issue_brief` 和 `data_issue_explainer`，输出纪律指标、关键规则、闭环条目、恢复队列和刷新步骤；不调用 Tushare/AkShare/yfinance/DeepSeek/GitHub、不运行回测或满血刷新、不重算 action、不执行真实交易、不修改持仓或 `strategy_execution_packet.action`。

`/api/legacy/cache` 已接入旧工作台桥接 / 迁移清单只读迁移：读取本地 `legacy_migration_map`、`legacy_packet_migration_checklist`、`old_workspace_packet_bridge`、`old_workspace_capability_overview`、`old_workspace_data_absence_ledger`、`legacy_decision_chain_summary` 和 `legacy_a_share_fact_recovery_actions`，输出旧功能迁移清单、旧 packet 桥接、缺失账本和调用血缘；不调用 Tushare/DeepSeek/GitHub、不打开 Streamlit、不运行旧工具、不执行真实交易、不修改持仓或 `strategy_execution_packet.action`。

`/api/evidence/cache` 已接入 A 股证据雷达与事实血缘只读迁移：读取本地 `command_center_evidence_radar_packet` / `a_share_fact_lineage_summary` 或用本地 builder 生成缓存视图；不调用 Tushare/DeepSeek/GitHub、不运行回测、不执行真实交易、不修改 `strategy_execution_packet.action`。

`/api/data-capability/cache` 已接入数据能力/数据源体检只读迁移：读取本地 `data_capability`、`data_capability_console` 与 `data_health_ledger`，或用本地 builder 生成安全空态；不 ping Tushare/AkShare/yfinance/Supabase，不调用 DeepSeek/GitHub，不执行真实交易，不修改 `strategy_execution_packet.action`。

`/api/data-health/cache` 已接入数据健康时间线 / Provider 诊断只读迁移：读取本地 `data_health_timeline`、`provider_data_capability_cockpit`、`a_share_capability_matrix`、`data_health_ledger`、`data_gap_report` 和数据健康恢复动作，输出历史健康状态、provider 诊断、能力矩阵、缺口和调用血缘；不 ping Tushare/AkShare/yfinance/Supabase，不调用 DeepSeek/GitHub，不刷新数据，不执行真实交易，不修改持仓或 `strategy_execution_packet.action`。

`/api/recovery/cache` 已接入数据恢复中心只读迁移：读取本地 `data_recovery_actions`、`tool_recovery_actions`、`recovery_result_timeline`、`data_health_timeline_recovery_actions`、`a_share_evidence_recovery_ledger`、`provider_recovery_matrix` 和 `data_gap_report`，输出恢复动作、恢复时间线和调用血缘；不调用 Tushare/AkShare/yfinance/DeepSeek/GitHub、不执行恢复动作、不刷新数据、不执行真实交易、不修改持仓或 `strategy_execution_packet.action`。

`/api/strategy/cache` 已接入策略执行 / 今日决策只读迁移：读取本地 `strategy_execution_packet` 与 `command_center_decision_packet`，输出 action 来源、策略 trace、决策摘要和调用血缘；不调用 Tushare/DeepSeek/GitHub、不运行回测、不执行真实交易、不修改 `strategy_execution_packet.action` 或 `command_center_decision_packet`。

`/api/position/cache` 已接入持仓画像 / 标的上下文只读迁移：读取本地 home snapshot 中的 `holding_action`、`position_risk_budget`、`risk_breakdown`、`safety_line` 和策略上下文；不刷新价格、不调用 Tushare/DeepSeek/GitHub、不执行真实交易、不修改持仓或 `strategy_execution_packet.action`。

`/api/candidate-radar/cache` 已接入下一票候选雷达只读迁移：读取本地 `radar_packet`、`next_ticket_candidates` 和候选证据恢复动作，输出候选分层、补证路线和调用血缘；不扫描全市场、不调用 Tushare/DeepSeek/GitHub、不执行真实交易、不把候选分数写入 `strategy_execution_packet.action`。

`/api/risk/cache` 已接入风险护栏 / 安全线只读迁移：读取本地 `risk_alerts`、`safety_line`、`execution_guardrail_overview`、`legacy_decision_chain_summary`、`strategy_prerequisite_recovery_ledger`、`position_risk_budget` 和 `risk_breakdown`，输出禁止事项、降风险条件、数据缺口、执行阻断和调用血缘；不调用 Tushare/DeepSeek/GitHub、不运行回测、不执行真实交易、不修改持仓或 `strategy_execution_packet.action`，也不清除风险标记。

## 当前 stub API

- `/api/factor-quant/refresh-data`
- `/api/chokepoint/run`
- `/api/serenity/github-probe`

这些 stub 只返回 `task_id` 和安全任务状态，不调用 Tushare、DeepSeek、GitHub，也不执行真实交易。
`/api/tasks` 已返回 `command_center_3_task_status_index`：包含本地任务列表、`pending/running/success/failed/cancelled` 状态计数、最新任务、`call_ledger_count`、外部调用标志和交易边界；React 页面可通过 `/api/tasks/{task_id}` 轮询单个任务。
`/api/tasks/{task_id}/cancel` 已接入本地任务生命周期控制：只将 pending/running 任务标记为 `cancelled`，写入 `local_task_cancel` 调用血缘；终态任务取消请求记录为 no-op；不调用 Tushare/DeepSeek/GitHub，不执行真实交易，不修改 `strategy_execution_packet.action`。
任务生命周期现在同步写入 `.stock_ming_3/meta.sqlite`；内存 fallback 丢失时，`/api/tasks/{task_id}` 仍可从 SQLite 读回任务状态。`/api/packets` 同时暴露 SQLite packet/task metadata 摘要，供 3.0 前端识别持久化 cache 来源。

`/api/factor-quant/run-light` 已从纯 stub 升级为本地 light-mode pipeline：只读取本地 snapshot/cache，生成 `command_center_factor_quant_hub_packet` 并写入 SQLite meta cache，同时把 `runtime.factor_values` 写入 Parquet；仍不调用 Tushare、DeepSeek、GitHub，不跑全市场回测，不修改 strategy action。

`/api/next-session/generate` 已从纯 stub 升级为本地 cache pipeline：只读取已有次日图谱 cache，发现精确 `command_center_next_session_projection_packet` 时写入 SQLite meta cache；没有精确 packet 时返回 `cache_missing` 任务状态，不写入假 packet。该任务仍不调用 Tushare、DeepSeek、GitHub，不修改 strategy action、价格、持仓或 operation_zones。

`/api/factor-quant/deepseek-explain` 已从纯 stub 升级为 guarded explanation pipeline：只读取已有 Factor Quant Hub cache，生成未发送的安全 prompt 预览；如传入本地解释 payload，只保留 `summary`、`support_notes`、`suppress_notes`、`conflict_notes`、`missing_data_notes`、`discipline_notes` 六类字段并写回 SQLite cache。当前阶段不真实调用 DeepSeek，不输出价格/持仓/因子值/买卖指令，不覆盖任何数值 packet。

`/api/trade-review/cache` 已接入交易记录实验室只读迁移：只读取 `.stock_ming_cache/trade_review_log.jsonl`，返回复盘记录摘要、记录表和本地读取血缘；不创建记录、不调用 Tushare/DeepSeek/GitHub、不执行真实交易、不修改 `strategy_execution_packet.action`。

`/api/quant/cache` 已接入旧量化/回测只读迁移：读取 `command_center_quant_packet` 或本地 snapshot 构建轻量缓存摘要；不运行 `backtester`、不调用 Tushare/DeepSeek/GitHub、不执行真实交易、不修改 `strategy_execution_packet.action`。完整回测后续必须通过按钮门控 POST task。
