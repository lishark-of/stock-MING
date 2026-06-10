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

Streamlit `app.py` 保留，但定位调整为 legacy/admin/debug，不再作为长期正式主入口；页面顶部已显示 Command Center 3.0 正式入口和 legacy/admin/debug 边界提示。

## 迁移进度基线

后续规划以这张基线为准，不在每轮重新估算方向：

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
- `POST /api/factor-quant/deepseek-explain`
- `GET /api/chokepoint/cache`
- `POST /api/chokepoint/run`
- `GET /api/serenity/cache`
- `POST /api/serenity/github-probe`
- `GET /api/storage`
- `GET /api/storage/catalog`
- `GET /api/storage/factor-values`
- `GET /api/storage/{dataset}`，当前白名单为 `factor_values`、`daily`、`daily_basic`、`moneyflow`、`backtest_results`
- `GET /api/tasks/catalog`
- `GET /api/tasks/{task_id}`

规则：

- `GET .../cache` 不触发 Tushare、DeepSeek、GitHub。
- `/health` 返回启动安全摘要；`GET /api/model-strategy/cache` 返回当前 DeepSeek 模型策略、用途映射和配置来源。二者都不包含 token/key，不触发模型调用。
- `/api/migration/status` 返回用户给定的 3.0 长期迁移进度基线、目标技术栈和安全原则；该接口只读、不外联、不重新估算进度。
- `/api/tasks/catalog` 返回按钮门控任务目录、可能外部源、call ledger 要求和交易边界；DeepSeek-capable 任务会声明 `deepseek_model_strategy_purpose`、配置键和非硬编码模型来源；该接口只读，不创建任务。
- `GET .../cache` 优先读取 `.stock_ming_cache/command_center_latest.json` 中已有本地快照；没有精确 packet 时返回 `cache_missing`，不会把旧 packet 冒充新 packet。
- `/api/packets/{packet_key}` 支持部分 2.0 本地快照别名，例如 `command_center_moneyflow_packet` → `moneyflow_packet`、`strategy_execution_packet` → `strategy_packet`。
- `POST` 默认返回 local fallback task，不在请求线程跑重计算；任务可通过 `/api/tasks/{task_id}` 轮询，记录 `pending → running → success` 状态历史、`progress`、`current_step`、`error_message_safe`、`output_packet_key` 和 `call_ledger`。DeepSeek-capable stub 和 guarded explanation task 会把集中模型策略引用写入 `call_ledger.request_params_safe`，但不会调用模型。
- 提交纪律保持为人工确认：不使用 `git add .`，不 push，除非用户明确确认。
- `/api/tasks` 返回 `command_center_3_task_status_index`，包含任务列表、状态计数、最新任务、`call_ledger_count` 和外部/交易边界汇总，供 3.0 前端状态面板与审计页展示。
- `POST /api/next-session/generate` 已从纯 stub 升级为本地 cache pipeline：读取已有 `command_center_next_session_projection_packet` cache，发现精确 packet 时写入 `.stock_ming_3/meta.sqlite`；没有精确 packet 时返回 `cache_missing` 任务结果且不写入假 packet。不调用 Tushare、DeepSeek、GitHub，不修改 `strategy action` 或 `operation_zones`。
- `POST /api/factor-quant/run-light` 已接入本地 light-mode pipeline：读取 `.stock_ming_cache/command_center_latest.json`，调用现有 Factor Quant Hub builder，写入 `.stock_ming_3/meta.sqlite`，并把 `runtime.factor_values` 同步写入 `.stock_ming_3/parquet/factor_values.parquet`；不调用 Tushare、DeepSeek、GitHub，也不修改 `strategy action`。
- `POST /api/factor-quant/deepseek-explain` 已接入 guarded explanation pipeline：读取 Factor Quant Hub cache，准备未发送的安全 prompt 预览；如提供本地解释 payload，仅按六个白名单字段清洗并写回 SQLite cache，不真实调用 DeepSeek、不覆盖数值、不修改 `strategy action`。
- 任务生命周期已同步写入 SQLite metadata store；内存状态丢失后，`/api/tasks/{task_id}` 仍可从本地 SQLite fallback 读回任务状态。
- `/api/packets` 已暴露 SQLite packet/task metadata 摘要，便于前端判断哪些 packet 来自持久化 cache。
- `/api/model-strategy/cache` 已独立暴露 DeepSeek 模型策略：`default/explain/projection/factor_explain` 默认走解释级模型，`fast/healthcheck/feeder` 默认走 fast 模型；模型名统一从 `DEEPSEEK_EXPLAIN_MODEL`、`DEEPSEEK_FAST_MODEL`、`DEEPSEEK_DEFAULT_MODEL` 或集中默认值读取，调用点、任务目录和任务回执不得硬编码。
- `GET /api/storage` 暴露 Parquet/DuckDB 的 `factor_values`、`daily`、`daily_basic`、`moneyflow`、`backtest_results` 只读状态和 dataset catalog；缺文件返回 `missing`，不触发 Tushare、回测或因子计算。
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
如果本机未安装 Rust/Cargo，只运行 Vite 前端即可；Tauri dev mode 需要安装 Rust 后再执行 `npm run tauri dev`。

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

### Storage

- SQLite：packet 元数据、任务状态、用户配置。当前已落地 packet payload、packet metadata 和 task lifecycle metadata。
- Parquet：daily、daily_basic、moneyflow、factor_values、backtest_results。当前已提供 `factor_values`、`daily`、`daily_basic`、`moneyflow`、`backtest_results` 文件状态接口和 dataset catalog，并由 light-mode 因子任务写入 `factor_values`。
- DuckDB：直接查询 Parquet。当前已提供 `factor_values`、`daily`、`daily_basic`、`moneyflow`、`backtest_results` 缺文件安全查询和只读状态 API。
- Redis：Celery broker、任务状态、热点 packet cache；未安装时可使用 memory fallback。

## 边界

- 不执行真实交易。
- 不自动下单。
- 不泄露 token/key。
- DeepSeek 只做解释整理，不作为数据源。
- Tushare、DeepSeek、GitHub 不在应用启动或 cache GET 时自动调用。
- 因子结果只进入 evidence_effects 预览，不修改 strategy action。
- Streamlit 仅作为 legacy/admin/debug 入口保留，普通主路径迁往 React/Vite/Tauri + FastAPI。
- 现有 packet key 保持不变。
- 不使用 `git add .`；每个提交必须按文件或 hunk 精确 staging。
- 不 push，等待用户确认。

## 后续阶段

1. 把当前本地快照 cache 读取进一步落到 SQLite/Redis 持久化 packet。
2. 把 `refresh_factor_data` 等 local fallback task stub 迁移到 Celery worker，并保留相同任务状态合同。
3. 将 `refresh_factor_data` 接入真实 Tushare 按钮任务，并把 daily / daily_basic / moneyflow 结果写入 DuckDB/Parquet。
4. 安装 Rust 后验证 Tauri dev mode；生产打包放到后续阶段。
5. 把 Streamlit 页面逐块迁移到 React/ECharts。
6. 最后将 Streamlit 仅保留为 legacy/admin/debug。
