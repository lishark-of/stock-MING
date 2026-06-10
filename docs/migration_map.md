# Command Center 3.0 Migration Map

| Streamlit/现有模块 | 当前文件 | 3.0 API | 3.0 前端页面 | 是否重计算 | 是否任务化 |
|---|---|---|---|---|---|
| 次日操作图谱 | `command_center_next_session_projection.py`, `app.py` | `GET /api/next-session/cache`, `POST /api/next-session/generate` | `NextSessionMap.tsx` | cache GET 不重算；没有精确新 packet 时返回 `cache_missing` | 是，POST 当前 stub |
| Factor Quant Hub | `command_center_factor_research.py`, `app.py` | `GET /api/factor-quant/cache`, `POST /api/factor-quant/refresh-data`, `POST /api/factor-quant/run-light` | `FactorQuantHub.tsx` | cache GET 读取本地快照上下文；refresh/run 后续重算 | 是，POST 当前 stub |
| A 股事实血缘 | `command_center_evidence_summary.py`, `command_center_*_packet.py` | `/api/packets/{packet_key}` 与后续 fact refresh task | `CommandCenterHome.tsx` / 后续证据页 | cache 不重算，支持本地快照别名 | 后续任务化 |
| Tushare 数据刷新 | `tushare_adapter.py`, `app.py` | 后续 `refresh_tushare_facts` task | Factor / Next Session / Evidence pages | 是 | 是，当前 stub |
| 交易记录实验室 | `trade_review_log.py`, `app.py` | 后续 `/api/trade-review/cache` | `LegacyTools.tsx` 迁移后独立页面 | 否 | 否 |
| 旧量化/回测 | `command_center_quant_packet.py`, `backtester.py` | 后续 `/api/backtest/run` | 后续 ECharts 回测页 | 是 | 是 |
| 产业链瓶颈扫描 | `command_center_analysis_methods.py`, `analysis_engine.py`, `app.py` | `GET /api/chokepoint/cache`, `POST /api/chokepoint/run` | `ChokepointScan.tsx` | cache GET 不外联；没有精确 packet 时只返回缺口和旧分析摘要 | 是，POST 当前 stub |
| Serenity 方法雷达 | `command_center_serenity_method_radar.py`, `app.py` | `GET /api/serenity/cache`, `POST /api/serenity/github-probe` | `SerenityMethodRadar.tsx` | cache 使用本地方法基线；probe 后续外联 | 是，POST 当前 stub |
| DeepSeek 解释器 | `analysis_engine.py`, `deepseek_safety.py`, `command_center_*` | `POST /api/factor-quant/deepseek-explain` 等 | 页面按钮 | 只解释已有结构化结果 | 是，当前 stub |
| Packet Registry | `command_center_packet_registry.py` | `GET /api/packets`, `GET /api/packets/{packet_key}` | `CommandCenterHome.tsx` | 否 | 否 |
| Streamlit 旧工作台 | `app.py`, `visual_components.py` | 无新增主 API；作为 legacy | `LegacyTools.tsx` | 旧入口保留 | 不新增 |

## 当前可用 API

- `/health`
- `/api/packets`
- `/api/packets/{packet_key}`
- `/api/next-session/cache`
- `/api/factor-quant/cache`
- `/api/serenity/cache`
- `/api/chokepoint/cache`
- `/api/tasks/{task_id}`
- `/api/tasks`

`GET` 类 cache API 当前已可读取 `.stock_ming_cache/command_center_latest.json` 中的本地快照或本地 builder 结果，不调用 Tushare、DeepSeek、GitHub。精确 packet 缺失时返回 `cache_missing`，并附带可审计的 legacy 快照摘要。

## 当前 stub API

- `/api/next-session/generate`
- `/api/factor-quant/refresh-data`
- `/api/factor-quant/run-light`
- `/api/factor-quant/deepseek-explain`
- `/api/chokepoint/run`
- `/api/serenity/github-probe`

这些 stub 只返回 `task_id` 和安全任务状态，不调用 Tushare、DeepSeek、GitHub，也不执行真实交易。
任务状态已经包含 `pending/running/success/failed/cancelled` 合同、`progress`、`current_step`、`error_message_safe`、`output_packet_key`、`call_ledger` 和本地 fallback backend；React 页面可通过 `/api/tasks/{task_id}` 轮询。
