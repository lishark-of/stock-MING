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

Streamlit `app.py` 保留，但定位调整为 legacy/admin/debug，不再作为长期正式主入口。

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
- `GET /api/packets`
- `GET /api/packets/{packet_key}`
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
- `GET /api/tasks/{task_id}`

规则：

- `GET .../cache` 不触发 Tushare、DeepSeek、GitHub。
- `GET .../cache` 优先读取 `.stock_ming_cache/command_center_latest.json` 中已有本地快照；没有精确 packet 时返回 `cache_missing`，不会把旧 packet 冒充新 packet。
- `/api/packets/{packet_key}` 支持部分 2.0 本地快照别名，例如 `command_center_moneyflow_packet` → `moneyflow_packet`、`strategy_execution_packet` → `strategy_packet`。
- `POST` 默认返回 local fallback task，不在请求线程跑重计算；任务可通过 `/api/tasks/{task_id}` 轮询，记录 `pending → running → success` 状态历史、`progress`、`current_step`、`error_message_safe`、`output_packet_key` 和 `call_ledger`。
- `/api/tasks` 返回当前本地 fallback 任务列表，供 3.0 前端状态面板展示。
- `POST /api/factor-quant/run-light` 已接入本地 light-mode pipeline：读取 `.stock_ming_cache/command_center_latest.json`，调用现有 Factor Quant Hub builder，写入 `.stock_ming_3/meta.sqlite`，不调用 Tushare、DeepSeek、GitHub，也不修改 `strategy action`。
- `POST /api/factor-quant/deepseek-explain` 已接入 guarded explanation pipeline：读取 Factor Quant Hub cache，准备未发送的安全 prompt 预览；如提供本地解释 payload，仅按六个白名单字段清洗并写回 SQLite cache，不真实调用 DeepSeek、不覆盖数值、不修改 `strategy action`。
- 任务生命周期已同步写入 SQLite metadata store；内存状态丢失后，`/api/tasks/{task_id}` 仍可从本地 SQLite fallback 读回任务状态。
- `/api/packets` 已暴露 SQLite packet/task metadata 摘要，便于前端判断哪些 packet 来自持久化 cache。
- `POST /api/factor-quant/refresh-data` 当前仍是安全 stub；真实 Tushare 刷新后续必须继续保持按钮门控和 call ledger。
- 所有响应使用统一 envelope：`ok/data/error/call_ledger/warnings`。

### Desktop

启动：

```bash
cd desktop
npm install
npm run dev
```

Tauri 开发：

```bash
cd desktop
npm install
npm run tauri dev
```

如果本机未安装 Rust/Tauri CLI，只运行 Vite 前端即可。

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
- Parquet：daily、daily_basic、moneyflow、factor_values、backtest_results。
- DuckDB：直接查询 Parquet。
- Redis：Celery broker、任务状态、热点 packet cache；未安装时可使用 memory fallback。

## 边界

- 不执行真实交易。
- 不自动下单。
- 不泄露 token/key。
- DeepSeek 只做解释整理，不作为数据源。
- Tushare、DeepSeek、GitHub 不在应用启动或 cache GET 时自动调用。
- 因子结果只进入 evidence_effects 预览，不修改 strategy action。
- 现有 packet key 保持不变。

## 后续阶段

1. 把当前本地快照 cache 读取进一步落到 SQLite/Redis 持久化 packet。
2. 把 `refresh_factor_data` 等 local fallback task stub 迁移到 Celery worker，并保留相同任务状态合同。
3. 将 `refresh_factor_data` 接入真实 Tushare 按钮任务，并把 daily / daily_basic / moneyflow 结果写入 DuckDB/Parquet。
4. 把 Streamlit 页面逐块迁移到 React/ECharts。
5. 最后将 Streamlit 仅保留为 legacy/admin/debug。
