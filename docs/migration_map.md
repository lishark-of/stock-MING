# Command Center 3.0 Migration Map

| Streamlit/现有模块 | 当前文件 | 3.0 API | 3.0 前端页面 | 是否重计算 | 是否任务化 |
|---|---|---|---|---|---|
| 次日操作图谱 | `command_center_next_session_projection.py`, `app.py` | `GET /api/next-session/cache`, `POST /api/next-session/generate` | `NextSessionMap.tsx` | cache GET 不重算；没有精确新 packet 时返回 `cache_missing` | 是，POST 当前 stub |
| Factor Quant Hub | `command_center_factor_research.py`, `app.py` | `GET /api/factor-quant/cache`, `POST /api/factor-quant/refresh-data`, `POST /api/factor-quant/run-light` | `FactorQuantHub.tsx` | cache GET 读取本地快照/SQLite；run-light 本地 light 计算并写入 factor_values Parquet；refresh-data 后续接 Tushare | 是，run-light 已本地 pipeline |
| A 股事实血缘 | `command_center_evidence_summary.py`, `command_center_*_packet.py` | `GET /api/evidence/cache`, `/api/packets/{packet_key}` 与后续 fact refresh task | `AShareEvidenceRadar.tsx` | cache 不重算，支持本地快照别名 | 后续任务化 |
| 数据能力/数据源体检 | `command_center_data_capability_console.py`, `command_center_data_health_ledger.py`, `app.py` | `GET /api/data-capability/cache`，后续 provider refresh task | `DataCapabilityConsole.tsx` | cache GET 不检测；只读本地能力 packet | 后续任务化 |
| Tushare 数据刷新 | `tushare_adapter.py`, `app.py` | 后续 `refresh_tushare_facts` task | Factor / Next Session / Evidence / Data Capability pages | 是 | 是，当前 stub |
| 交易记录实验室 | `trade_review_log.py`, `app.py` | `GET /api/trade-review/cache` | `TradeReviewLab.tsx` | 否，cache-only 读取本地 `trade_review_log.jsonl` | 否 |
| 旧量化/回测 | `command_center_quant_packet.py`, `backtester.py` | `GET /api/quant/cache`，后续 `/api/backtest/run` | `QuantBacktestLab.tsx` | cache GET 不重算；后续 POST task 才可运行回测 | 后续任务化 |
| 产业链瓶颈扫描 | `command_center_analysis_methods.py`, `analysis_engine.py`, `app.py` | `GET /api/chokepoint/cache`, `POST /api/chokepoint/run` | `ChokepointScan.tsx` | cache GET 不外联；没有精确 packet 时只返回缺口和旧分析摘要 | 是，POST 当前 stub |
| Serenity 方法雷达 | `command_center_serenity_method_radar.py`, `app.py` | `GET /api/serenity/cache`, `POST /api/serenity/github-probe` | `SerenityMethodRadar.tsx` | cache 使用本地方法基线；probe 后续外联 | 是，POST 当前 stub |
| DeepSeek 解释器 | `analysis_engine.py`, `deepseek_safety.py`, `command_center_*` | `POST /api/factor-quant/deepseek-explain` 等 | 页面按钮 | 只解释已有结构化结果 | 是，当前 stub |
| Packet Registry | `command_center_packet_registry.py` | `GET /api/packets`, `GET /api/packets/{packet_key}` | `CommandCenterHome.tsx` | 否 | 否 |
| Storage datasets | `storage/parquet_store.py`, `storage/duckdb_store.py` | `GET /api/storage`, `GET /api/storage/{dataset}` | `CommandCenterHome.tsx` | 否，只读 Parquet/DuckDB 状态；白名单 `factor_values/daily/moneyflow` | 否 |
| Tauri desktop shell | `desktop/src-tauri/*`, `scripts/check_tauri_env.sh` | 连接本地 FastAPI `8710` | Tauri window / Vite dev | 否，预检不启动 Tauri | 否 |
| Streamlit 旧工作台 | `app.py`, `visual_components.py` | 无新增主 API；作为 legacy | `LegacyTools.tsx` | 旧入口保留 | 不新增 |

## 当前可用 API

- `/health`
- `/api/packets`
- `/api/packets/{packet_key}`
- `/api/evidence/cache`
- `/api/data-capability/cache`
- `/api/next-session/cache`
- `/api/factor-quant/cache`
- `/api/serenity/cache`
- `/api/chokepoint/cache`
- `/api/storage`
- `/api/storage/factor-values`
- `/api/storage/{dataset}`
- `/api/trade-review/cache`
- `/api/quant/cache`
- `/api/tasks/{task_id}`
- `/api/tasks`

`GET` 类 cache API 当前已可读取 `.stock_ming_cache/command_center_latest.json` 中的本地快照或本地 builder 结果，不调用 Tushare、DeepSeek、GitHub。精确 packet 缺失时返回 `cache_missing`，并附带可审计的 legacy 快照摘要。

`/api/evidence/cache` 已接入 A 股证据雷达与事实血缘只读迁移：读取本地 `command_center_evidence_radar_packet` / `a_share_fact_lineage_summary` 或用本地 builder 生成缓存视图；不调用 Tushare/DeepSeek/GitHub、不运行回测、不执行真实交易、不修改 `strategy_execution_packet.action`。

`/api/data-capability/cache` 已接入数据能力/数据源体检只读迁移：读取本地 `data_capability`、`data_capability_console` 与 `data_health_ledger`，或用本地 builder 生成安全空态；不 ping Tushare/AkShare/yfinance/Supabase，不调用 DeepSeek/GitHub，不执行真实交易，不修改 `strategy_execution_packet.action`。

## 当前 stub API

- `/api/next-session/generate`
- `/api/factor-quant/refresh-data`
- `/api/chokepoint/run`
- `/api/serenity/github-probe`

这些 stub 只返回 `task_id` 和安全任务状态，不调用 Tushare、DeepSeek、GitHub，也不执行真实交易。
任务状态已经包含 `pending/running/success/failed/cancelled` 合同、`progress`、`current_step`、`error_message_safe`、`output_packet_key`、`call_ledger` 和本地 fallback backend；React 页面可通过 `/api/tasks/{task_id}` 轮询。
任务生命周期现在同步写入 `.stock_ming_3/meta.sqlite`；内存 fallback 丢失时，`/api/tasks/{task_id}` 仍可从 SQLite 读回任务状态。`/api/packets` 同时暴露 SQLite packet/task metadata 摘要，供 3.0 前端识别持久化 cache 来源。

`/api/factor-quant/run-light` 已从纯 stub 升级为本地 light-mode pipeline：只读取本地 snapshot/cache，生成 `command_center_factor_quant_hub_packet` 并写入 SQLite meta cache，同时把 `runtime.factor_values` 写入 Parquet；仍不调用 Tushare、DeepSeek、GitHub，不跑全市场回测，不修改 strategy action。

`/api/factor-quant/deepseek-explain` 已从纯 stub 升级为 guarded explanation pipeline：只读取已有 Factor Quant Hub cache，生成未发送的安全 prompt 预览；如传入本地解释 payload，只保留 `summary`、`support_notes`、`suppress_notes`、`conflict_notes`、`missing_data_notes`、`discipline_notes` 六类字段并写回 SQLite cache。当前阶段不真实调用 DeepSeek，不输出价格/持仓/因子值/买卖指令，不覆盖任何数值 packet。

`/api/trade-review/cache` 已接入交易记录实验室只读迁移：只读取 `.stock_ming_cache/trade_review_log.jsonl`，返回复盘记录摘要、记录表和本地读取血缘；不创建记录、不调用 Tushare/DeepSeek/GitHub、不执行真实交易、不修改 `strategy_execution_packet.action`。

`/api/quant/cache` 已接入旧量化/回测只读迁移：读取 `command_center_quant_packet` 或本地 snapshot 构建轻量缓存摘要；不运行 `backtester`、不调用 Tushare/DeepSeek/GitHub、不执行真实交易、不修改 `strategy_execution_packet.action`。完整回测后续必须通过按钮门控 POST task。
