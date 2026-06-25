import { useEffect, useState } from "react";
import { cancelTask, getTaskCatalog, getTasks, postTask, retryTask, type TaskCreationEnvelope, type TaskRecord, type TaskStatusIndex } from "../api/client";
import DataLineageTable from "../components/DataLineageTable";
import JsonDetails from "../components/JsonDetails";
import MetricGrid from "../components/MetricGrid";
import PageStateBanner from "../components/PageStateBanner";
import PacketCard from "../components/PacketCard";
import StatusBadge from "../components/StatusBadge";
import TaskLaunchReceipt from "../components/TaskLaunchReceipt";
import TaskStatusPanel from "../components/TaskStatusPanel";

const CANDIDATE_CONFIRM_HREF = "#candidates/candidate-radar-search-quant-projection";

export default function TaskCatalog() {
  const [catalog, setCatalog] = useState<Record<string, unknown>>({});
  const [catalogEnvelopeLedger, setCatalogEnvelopeLedger] = useState<Array<Record<string, unknown>>>([]);
  const [catalogEnvelopeWarnings, setCatalogEnvelopeWarnings] = useState<Array<unknown>>([]);
  const [taskIndex, setTaskIndex] = useState<TaskStatusIndex | null>(null);
  const [taskIndexEnvelopeLedger, setTaskIndexEnvelopeLedger] = useState<Array<Record<string, unknown>>>([]);
  const [taskIndexEnvelopeWarnings, setTaskIndexEnvelopeWarnings] = useState<Array<unknown>>([]);
  const [taskRecords, setTaskRecords] = useState<TaskRecord[]>([]);
  const [selectedTaskId, setSelectedTaskId] = useState("");
  const [taskReceipt, setTaskReceipt] = useState<TaskCreationEnvelope | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const refreshTasks = () => {
    setError("");
    void getTasks().then((res) => {
      setTaskIndexEnvelopeLedger(res.call_ledger ?? []);
      setTaskIndexEnvelopeWarnings(res.warnings ?? []);
      setTaskIndex(res.data);
      const records = res.data.tasks ?? [];
      setTaskRecords(records);
      setSelectedTaskId((current) => current || res.data.latest_task_id || records[0]?.task_id || "");
      if (!res.ok) setError(res.error ?? "task_index_not_ok");
    }).catch((err) => {
      setError(err instanceof Error ? err.message : String(err));
    });
  };

  useEffect(() => {
    setLoading(true);
    setError("");
    const catalogPromise = getTaskCatalog().then((res) => {
      setCatalogEnvelopeLedger(res.call_ledger ?? []);
      setCatalogEnvelopeWarnings(res.warnings ?? []);
      setCatalog(res.data);
      if (!res.ok) setError(res.error ?? "task_catalog_not_ok");
      return res;
    });
    const tasksPromise = getTasks().then((res) => {
      setTaskIndexEnvelopeLedger(res.call_ledger ?? []);
      setTaskIndexEnvelopeWarnings(res.warnings ?? []);
      setTaskIndex(res.data);
      const records = res.data.tasks ?? [];
      setTaskRecords(records);
      setSelectedTaskId((current) => current || res.data.latest_task_id || records[0]?.task_id || "");
      if (!res.ok) setError(res.error ?? "task_index_not_ok");
      return res;
    });
    void Promise.allSettled([catalogPromise, tasksPromise]).then((results) => {
      const failed = results.find((item) => item.status === "rejected");
      if (failed?.status === "rejected") setError(failed.reason instanceof Error ? failed.reason.message : String(failed.reason));
      setLoading(false);
    });
  }, []);

  const launchTushareRefresh = () =>
    void postTask("/api/tasks/refresh-tushare-facts", { apis: ["daily", "daily_basic", "moneyflow"] }).then((res) => {
      setTaskReceipt(res);
      if (res.ok) {
        setSelectedTaskId(res.data.task_id);
        refreshTasks();
      }
    });

  const policy = catalog.policy as Record<string, unknown> | undefined;
  const catalogTasks = catalog.tasks as Array<Record<string, unknown>> | undefined;
  const taskLifecycleRoutes = catalog.task_lifecycle_routes as Array<Record<string, unknown>> | undefined;
  const routeCoverage = catalog.route_coverage as Record<string, unknown> | undefined;
  const implementationStatus = catalog.implementation_status as Record<string, unknown> | undefined;
  const externalSources = catalog.external_sources as unknown[] | undefined;
  const knownPostRouteRows = Array.isArray(routeCoverage?.known_post_routes)
    ? (routeCoverage?.known_post_routes as unknown[]).map((route, index) => ({ index: index + 1, route: String(route), coverage: "known_post_route" }))
    : [];
  const uncoveredPostRouteRows = Array.isArray(routeCoverage?.uncovered_post_routes)
    ? (routeCoverage?.uncovered_post_routes as unknown[]).map((route, index) => ({ index: index + 1, route: String(route), coverage: "uncovered_post_route" }))
    : [];
  const taskIndexPolicy = taskIndex?.policy ?? {};
  const taskStatusRows = Object.entries(taskIndex?.status_counts ?? {}).map(([status, count]) => ({ status, count }));
  const catalogPayloadLedger = (catalog.call_ledger as Array<Record<string, unknown>> | undefined) ?? [];
  const catalogCallLedger = catalogEnvelopeLedger.length ? catalogEnvelopeLedger : catalogPayloadLedger;
  const catalogWarnings = catalogEnvelopeWarnings.length ? catalogEnvelopeWarnings : ((catalog.warnings as Array<unknown> | undefined) ?? []);
  const taskIndexPayloadLedger = taskIndex?.call_ledger ?? [];
  const taskIndexCallLedger = taskIndexEnvelopeLedger.length ? taskIndexEnvelopeLedger : taskIndexPayloadLedger;
  const taskIndexWarnings = taskIndexEnvelopeWarnings.length ? taskIndexEnvelopeWarnings : (taskIndex?.warnings ?? []);
  const taskPersistence = taskIndex?.persistence ?? {};
  const taskPersistenceRows = taskIndex?.persistence_source_rows ?? [];
  const backendCountRows = Object.entries((implementationStatus?.backend_counts as Record<string, unknown> | undefined) ?? {}).map(([backend, count]) => ({
    backend,
    count
  }));
  const implementationTypeRows = [
    { kind: "stub", count: implementationStatus?.stub_task_count, task_types: Array.isArray(implementationStatus?.stub_task_types) ? (implementationStatus?.stub_task_types as unknown[]).join(" / ") : "" },
    { kind: "local_pipeline", count: implementationStatus?.local_pipeline_task_count, task_types: Array.isArray(implementationStatus?.local_pipeline_task_types) ? (implementationStatus?.local_pipeline_task_types as unknown[]).join(" / ") : "" },
    { kind: "guarded_local", count: implementationStatus?.guarded_local_task_count, task_types: Array.isArray(implementationStatus?.guarded_local_task_types) ? (implementationStatus?.guarded_local_task_types as unknown[]).join(" / ") : "" },
    { kind: "external_capable", count: implementationStatus?.external_capable_task_count, task_types: Array.isArray(implementationStatus?.external_capable_task_types) ? (implementationStatus?.external_capable_task_types as unknown[]).join(" / ") : "" }
  ];
  const deepseekModelStrategyRows = (catalogTasks ?? [])
    .filter((item) => Array.isArray(item.possible_external_sources) && item.possible_external_sources.includes("deepseek"))
    .map((item) => {
      const strategy = (item.deepseek_model_strategy as Record<string, unknown> | undefined) ?? {};
      return {
        task_type: item.task_type,
        route: item.route,
        model_purpose: item.deepseek_model_strategy_purpose ?? "not_declared",
        model: strategy.model ?? "--",
        config_keys: Array.isArray(strategy.config_keys) ? strategy.config_keys.join(" / ") : item.deepseek_model_config_keys,
        active_config_key: strategy.active_config_key ?? "--",
        model_source: strategy.model_source ?? item.deepseek_model_source ?? "",
        does_not_hardcode_deepseek_model: item.does_not_hardcode_deepseek_model === true,
        no_hardcoded_model: strategy.does_not_hardcode_model === true,
        contains_secret: strategy.contains_secret === true,
        cache_read_external_call: strategy.external_call_on_cache_read === true,
        button_gated: item.button_gated === true,
        call_ledger_required: item.call_ledger_required === true
      };
    });
  const taskRows = taskRecords.map((task) => ({
    task_id: task.task_id,
    task_type: task.task_type,
    status: task.status,
    progress: task.progress,
    current_step: task.current_step,
    output_packet_key: task.output_packet_key,
    backend: task.backend ?? "local_fallback",
    storage_source: task.storage_source ?? "memory_or_sqlite_fallback",
    call_ledger_count: task.call_ledger?.length ?? 0,
    external_calls_triggered: task.external_calls_triggered === true,
    tushare_called: task.tushare_called === true,
    source_task_tushare_called: task.source_task_tushare_called === true || task.call_ledger_tushare_replayed === true,
    source_task_provider_ledger_replayed: task.source_task_provider_ledger_replayed === true || task.call_ledger_external_calls_replayed === true,
    readback_external_calls_triggered: task.readback_external_calls_triggered === true,
    deepseek_called: task.deepseek_called === true,
    github_called: task.github_called === true,
    does_not_execute_trades: task.does_not_execute_trades !== false,
    does_not_modify_strategy_action: task.does_not_modify_strategy_action !== false
  }));
  const routeCoverageRows = [
    ...(catalogTasks ?? []).map((item) => ({
      route_type: "task_creation",
      route: item.route,
      task_type: item.task_type,
      button_gated: item.button_gated,
      call_ledger_required: item.call_ledger_required,
      external_call_policy: item.external_call_policy,
      possible_external_sources: Array.isArray(item.possible_external_sources) ? item.possible_external_sources.join(" / ") : ""
    })),
    ...(taskLifecycleRoutes ?? []).map((item) => ({
      route_type: item.route_type ?? "local_lifecycle",
      route: item.route,
      task_type: "local_task_lifecycle",
      button_gated: item.button_gated,
      call_ledger_required: item.call_ledger_required,
      external_call_policy: item.external_call_policy,
      possible_external_sources: Array.isArray(item.possible_external_sources) ? item.possible_external_sources.join(" / ") : ""
    }))
  ];
  const taskCatalogLatestTask =
    taskRecords.find((task) => task.task_id === selectedTaskId) ??
    taskRecords.find((task) => task.task_id === taskIndex?.latest_task_id) ??
    taskRecords[0];
  const taskCatalogLatestTaskLedger = taskCatalogLatestTask?.call_ledger ?? [];
  const taskCatalogLatestTushareRows = taskCatalogLatestTaskLedger.filter((row) => row.tushare_called === true);
  const taskCatalogLatestTushareSuccessCount = taskCatalogLatestTushareRows.filter((row) => String(row.call_status ?? "") === "success").length;
  const taskCatalogLatestSourceTushareReplayed =
    taskCatalogLatestTask?.source_task_tushare_called === true ||
    taskCatalogLatestTask?.call_ledger_tushare_replayed === true ||
    taskCatalogLatestTushareRows.length > 0;
  const taskCatalogLatestReadbackExternal =
    taskCatalogLatestTask?.readback_external_calls_triggered === true ||
    taskIndex?.readback_external_calls_triggered === true;
  const taskCatalogLatestIsCandidateReplay =
    taskCatalogLatestTask?.output_packet_key === "command_center_3_candidate_radar_cache" ||
    String(taskCatalogLatestTask?.task_type ?? "").includes("candidate_radar_quant_projection");
  const taskCatalogOrdinaryTaskStatusLabel = taskCatalogLatestTask
    ? `${taskCatalogLatestTask.status} / ${taskCatalogLatestTask.current_step}`
    : "等待下一票雷达确认按钮创建任务";
  const taskCatalogOrdinaryP2Label = taskCatalogLatestTask
    ? taskCatalogLatestTask.status === "success"
      ? "任务已完成；可刷新 cache / ledger / packet 回放"
      : "等待任务完成后回放 cache / ledger / packet"
    : "暂无任务；先回下一票雷达确认输入区输入代码并确认";
  const taskCatalogOrdinaryTushareLabel = taskCatalogLatestTushareRows.length
    ? `Tushare-first ${taskCatalogLatestTushareSuccessCount}/${taskCatalogLatestTushareRows.length} 已写入 task.call_ledger`
    : taskCatalogLatestSourceTushareReplayed
      ? "Tushare-first ledger 已从 CandidateRadar cache 回放"
    : taskCatalogLatestIsCandidateReplay
      ? "等待 Tushare-first ledger"
      : "非搜票任务按输出 packet 回放";
  const taskCatalogOrdinaryReadbackLabel = taskCatalogLatestTask
    ? taskCatalogLatestReadbackExternal
      ? "异常：任务状态读取触发外联，需先排障"
      : taskCatalogLatestSourceTushareReplayed
        ? "GET 只读回放源任务 Tushare ledger；本次刷新无新增外联"
        : "GET 只读读取任务状态；未回放 provider ledger"
    : "等待任务记录";
  const taskCatalogOrdinaryP3Label = taskCatalogLatestIsCandidateReplay
    ? taskCatalogLatestTask?.status === "success"
      ? "可打开股票量化推演和次日图谱"
      : "任务完成后再打开量化推演和次日图谱"
    : taskCatalogLatestTask?.output_packet_key
      ? `按 ${taskCatalogLatestTask.output_packet_key} 回放`
      : "等待输出 packet";
  const taskCatalogOrdinaryProgressItems = [
    { label: "当前任务", value: taskCatalogLatestTask?.task_id ?? "暂无任务记录", tone: taskCatalogLatestTask ? "good" as const : "warn" as const },
    { label: "任务状态", value: taskCatalogOrdinaryTaskStatusLabel, tone: taskCatalogLatestTask?.status === "success" ? "good" as const : taskCatalogLatestTask ? "warn" as const : "warn" as const },
    { label: "P2 写回", value: taskCatalogOrdinaryP2Label, tone: taskCatalogLatestTask?.status === "success" ? "good" as const : "warn" as const },
    { label: "Tushare-first", value: taskCatalogOrdinaryTushareLabel, tone: taskCatalogLatestTushareRows.length ? "good" as const : "warn" as const },
    { label: "读取方式", value: taskCatalogOrdinaryReadbackLabel, tone: taskCatalogLatestReadbackExternal ? "bad" as const : taskCatalogLatestTask ? "good" as const : "warn" as const },
    { label: "P3 结果入口", value: taskCatalogOrdinaryP3Label, tone: taskCatalogLatestTask?.status === "success" ? "good" as const : "warn" as const },
    { label: "安全边界", value: "Task Monitor 只读 GET /api/tasks；不创建 task、不补调 Tushare/DeepSeek、不交易", tone: "good" as const }
  ];
  const empty = !loading && !error && !catalogTasks?.length && !taskRecords.length;

  return (
    <>
      <div className="page-head">
        <h1>Task Monitor / 任务监控</h1>
        <StatusBadge label={String(catalog.status ?? "catalog")} tone={catalog.status === "ready" ? "good" : "neutral"} />
      </div>

      <PageStateBanner
        loading={loading}
        error={error}
        empty={empty}
        emptyTitle="暂无任务目录或任务记录"
        emptyDetail="本页只读任务目录和任务状态；POST task 必须由各业务页按钮触发。"
      />

      <PacketCard title="普通任务进度速读" subtitle="确认按钮之后先看这里；工程目录和路由覆盖继续下沉" status={taskCatalogLatestTask?.status ?? "waiting_task"}>
        <MetricGrid items={taskCatalogOrdinaryProgressItems} />
        <p className="risk-note">Tushare-first 显示的是源任务 call_ledger 回放；“刷新任务状态”只是 GET /api/tasks，只读、不新增外联。</p>
        <div className="actions" aria-label="task monitor ordinary progress actions">
          <button onClick={refreshTasks} title="只重新读取 GET /api/tasks；不创建 task、不调用 provider/model" aria-label="refresh task monitor ordinary progress">刷新任务状态</button>
          <a href={CANDIDATE_CONFIRM_HREF} title="切换到下一票雷达确认输入区；输入代码仍需确认按钮" aria-label="open candidate radar confirm input from task monitor ordinary progress">下一票雷达确认</a>
          <a href="#factor" title="切换到股票量化推演；只读本地回放" aria-label="open stock quant from task monitor ordinary progress">股票量化推演</a>
          <a href="#next" title="切换到次日图谱；只读本地回放" aria-label="open next session from task monitor ordinary progress">次日图谱</a>
        </div>
        <p className="risk-note">这张卡只读 task index 和当前选择任务；刷新按钮只调用本地 GET /api/tasks，不会创建第二个 task、不调用 Tushare/DeepSeek/GitHub、不读取 token/key、不执行真实交易。</p>
      </PacketCard>

      <MetricGrid
        items={[
          { label: "任务数量", value: catalog.task_count as number | undefined },
          { label: "任务记录", value: taskIndex?.task_count ?? taskRecords.length },
          { label: "任务 call_ledger", value: taskIndex?.call_ledger_count ?? 0 },
          { label: "stub tasks", value: implementationStatus?.stub_task_count as number | undefined },
          { label: "local pipelines", value: implementationStatus?.local_pipeline_task_count as number | undefined },
          { label: "guarded local", value: implementationStatus?.guarded_local_task_count as number | undefined },
          { label: "external capable", value: implementationStatus?.external_capable_task_count as number | undefined },
          { label: "memory tasks", value: taskPersistence.memory_task_count as number | undefined },
          { label: "sqlite tasks", value: taskPersistence.sqlite_task_count as number | undefined },
          { label: "去重任务", value: taskPersistence.deduplicated_task_count as number | undefined },
          { label: "已登记 POST", value: routeCoverage?.known_post_route_count as number | undefined },
          { label: "未覆盖 POST", value: (routeCoverage?.uncovered_post_routes as unknown[] | undefined)?.length ?? 0, tone: (routeCoverage?.uncovered_post_routes as unknown[] | undefined)?.length ? "bad" : "good" },
          { label: "catalog envelope ledger", value: catalogCallLedger.length },
          { label: "catalog warnings", value: catalogWarnings.length },
          { label: "task index envelope ledger", value: taskIndexCallLedger.length },
          { label: "task index warnings", value: taskIndexWarnings.length },
          { label: "任务外联", value: taskIndex?.external_calls_triggered === true ? "存在" : "无", tone: taskIndex?.external_calls_triggered === true ? "bad" : "good" },
          { label: "任务真实交易", value: taskIndex?.does_not_execute_trades === false ? "可能" : "禁止", tone: taskIndex?.does_not_execute_trades === false ? "bad" : "good" },
          { label: "全部按钮门控", value: policy?.all_tasks_button_gated, tone: policy?.all_tasks_button_gated === false ? "bad" : "good" },
          { label: "POST 全部登记", value: policy?.all_known_post_routes_button_gated, tone: policy?.all_known_post_routes_button_gated === false ? "bad" : "good" },
          { label: "call ledger required", value: policy?.call_ledger_required_for_all, tone: policy?.call_ledger_required_for_all === false ? "bad" : "good" },
          { label: "cache API 外联", value: policy?.cache_api_external_calls === true ? "存在" : "无", tone: policy?.cache_api_external_calls === true ? "bad" : "good" },
          { label: "真实交易", value: policy?.does_not_execute_trades === false ? "可能" : "禁止", tone: policy?.does_not_execute_trades === false ? "bad" : "good" },
          { label: "修改 action", value: policy?.does_not_modify_strategy_action === false ? "可能" : "不会", tone: policy?.does_not_modify_strategy_action === false ? "bad" : "good" },
          { label: "外部源", value: externalSources?.join(" / ") || "无" },
          { label: "已触发外部调用", value: catalog.external_calls_triggered === true ? "是" : "否", tone: catalog.external_calls_triggered === true ? "bad" : "good" }
        ]}
      />

      <div className="grid">
        <PacketCard title="Tushare 刷新任务" subtitle="按钮门控 POST /api/tasks/refresh-tushare-facts；GET cache 不会触发" status="button_gated">
          <p>默认只刷新 daily / daily_basic / moneyflow；任务会写 call_ledger，不打印 token/key，不修改 strategy action。</p>
          <p>日历接口 trade_cal 与 margin / limit / cyq / hard-risk 扩展接口只在按钮 payload 明确选择或 include_extended 时进入验证；trade_cal 可落 Parquet，其他扩展接口默认只写审计状态，不会伪装成落盘完成。</p>
          <p>任务 packet 会输出 api_validation_rows 和 api_acceptance_audit：前者区分 matrix_only / validated / partial_failed / blocked，后者只审计 call_ledger 字段、安全状态、未选接口不误标 verified 和非 Parquet 接口不假写入。</p>
          <p>provider_acceptance_readiness_audit 只汇总全接口生产验收阻断项；provider_acceptance_pending / provider_backed_acceptance_done=false 表示还没有真实 provider-backed 全接口验收。</p>
          <p>provider_sample_activation_receipt 是显式 provider 样本验收前的本地清单：不调用 Tushare、不创建任务、不把 matrix/local QA/gap ledger 当 provider-backed acceptance，也不宣称 production_tushare_pipeline_complete。</p>
          <p>provider_target_sample_execution_recipe 只固定下一次 target-sample provider 验收的人工确认、POST task、call_ledger、failure mode、promotion review 顺序；不调用 Tushare、不创建任务、不等于 full-interface acceptance。</p>
          <p>tushare_durable_evidence_recipe 只固定 LTG-02 target samples、safe call ledger、failure mode、full-interface promotion 和 storage/cache promotion 的直接证据缺口；不调用 Tushare、不创建任务、不代表 production_tushare_pipeline_complete。</p>
          <button onClick={launchTushareRefresh}>刷新 Tushare facts</button>
          <TaskLaunchReceipt receipt={taskReceipt} />
        </PacketCard>

        <PacketCard title="任务边界" subtitle="只读任务目录；不会创建任务；POST task 才可能触发外部请求" status="read_only">
          <p>本页只读取 FastAPI 的任务目录 cache 和 GET /api/tasks 任务记录，不调用 Tushare、DeepSeek 或 GitHub。</p>
          <p>任务执行必须由对应 POST API 按钮触发，并且需要写入 call_ledger_required_for_all 对应的审计记录。</p>
          <p>does_not_execute_trades 与 does_not_modify_strategy_action 必须保持为 true。</p>
          <p>task_status_index: {String(taskIndex?.packet_key ?? "--")}；get_tasks_cache_only: {String(taskIndexPolicy.get_tasks_cache_only ?? true)}</p>
          <p>storage_backend: {String(taskPersistence.storage_backend ?? "memory_plus_sqlite_fallback")}；task rows include storage_source: {String(taskPersistence.task_rows_include_storage_source ?? true)}</p>
        </PacketCard>

        <PacketCard title="任务实现状态" subtitle="区分 stub、local pipeline 与 guarded local，避免把 3.0 skeleton 误读成完整迁移" status={String(implementationStatus?.status ?? "partial_migration")}>
          <p>implementation scope: {String(implementationStatus?.scope ?? "command_center_3_task_backend_implementation")}</p>
          <p>implemented local task count: {String(implementationStatus?.implemented_local_task_count ?? 0)}</p>
          <p>stub tasks must not be reported as complete: {String(policy?.stub_tasks_must_not_be_reported_as_complete ?? true)}</p>
          <p>external capable tasks button gated: {String(implementationStatus?.all_external_capable_tasks_are_button_gated ?? true)}</p>
          <p>external capable tasks require call ledger: {String(implementationStatus?.all_external_capable_tasks_require_call_ledger ?? true)}</p>
          <DataLineageTable rows={implementationTypeRows} />
          <h3>backend counts</h3>
          <DataLineageTable rows={backendCountRows} />
        </PacketCard>

        <PacketCard title="外部请求策略" subtitle="GET catalog 不外联；按钮任务才可能进入外部源" status={String(policy?.post_task_may_trigger_external_request ?? true)}>
          <p>possible external sources: {externalSources?.join(", ") || "none"}</p>
          <p>Tushare called: {String(catalog.tushare_called ?? false)}</p>
          <p>DeepSeek called: {String(catalog.deepseek_called ?? false)}</p>
          <p>GitHub called: {String(catalog.github_called ?? false)}</p>
        </PacketCard>
      </div>

      <PacketCard title="任务清单" subtitle="按钮门控、可能外部源和输出 packet" status="catalog">
        <DataLineageTable rows={catalogTasks ?? []} />
      </PacketCard>

      <PacketCard title="DeepSeek 任务模型策略" subtitle="只读展示按钮任务的模型用途；真实调用仍需 POST task 和 call_ledger" status="model_strategy">
        <p>DeepSeek 相关任务必须通过 DEEPSEEK_EXPLAIN_MODEL / DEEPSEEK_DEFAULT_MODEL 等集中配置选择模型，不能在任务或页面里硬编码模型名。</p>
        <p>本卡片只读取 GET /api/tasks/catalog，不调用 DeepSeek、不读取 token/key、不执行真实交易。</p>
        <DataLineageTable rows={deepseekModelStrategyRows} />
      </PacketCard>

      <PacketCard title="POST 路由覆盖" subtitle="任务创建 POST 与本地生命周期 POST 分开登记；cache GET 不创建任务" status="route_coverage">
        <p>known_post_route_count: {String(routeCoverage?.known_post_route_count ?? 0)}</p>
        <p>uncovered_post_routes: {String((routeCoverage?.uncovered_post_routes as unknown[] | undefined)?.length ?? 0)}</p>
        <p>all_known_post_routes_button_gated: {String(routeCoverage?.all_known_post_routes_button_gated ?? false)}</p>
        <p>call_ledger_required_for_all_known_post_routes: {String(routeCoverage?.call_ledger_required_for_all_known_post_routes ?? false)}</p>
        <p>cancel_routes_external_calls: {String(routeCoverage?.cancel_routes_external_calls ?? false)}</p>
        <p>retry_routes_external_calls: {String(routeCoverage?.retry_routes_external_calls ?? false)}</p>
        <DataLineageTable rows={routeCoverageRows} />
        <h3>已登记 POST 路由</h3>
        <DataLineageTable rows={knownPostRouteRows} />
        <h3>未覆盖 POST 路由</h3>
        <DataLineageTable rows={uncoveredPostRouteRows} />
      </PacketCard>

      <PacketCard title="任务目录 envelope call_ledger" subtitle="GET /api/tasks/catalog 顶层响应血缘；只读、不外联、不交易" status="lineage">
        <DataLineageTable rows={catalogCallLedger} />
      </PacketCard>

      <PacketCard title="任务状态总览" subtitle="GET /api/tasks 返回 command_center_3_task_status_index；只读汇总" status="task_status_index">
        <DataLineageTable rows={taskStatusRows} />
        <h3>任务持久化来源</h3>
        <DataLineageTable rows={taskPersistenceRows} />
        <DataLineageTable rows={taskIndexCallLedger} />
      </PacketCard>

      <PacketCard title="任务记录" subtitle="GET /api/tasks 只读状态；不会创建任务" status="read_only">
        <DataLineageTable rows={taskRows} />
      </PacketCard>

      <PacketCard title="任务详情轮询" subtitle="选择任务后轮询 GET /api/tasks/{task_id}；不创建任务、不外联" status={selectedTaskId ? "selected" : "empty"}>
        <p>详情面板复用 TaskStatusPanel，会展示单任务 call_ledger、status_history 和本地取消入口。</p>
        <p>读取路径仍然是 FastAPI GET cache；不会调用 Tushare、DeepSeek 或 GitHub。</p>
        <div className="button-row">
          {taskRecords.map((task) => (
            <button
              key={task.task_id}
              className={selectedTaskId === task.task_id ? "secondary" : undefined}
              onClick={() => setSelectedTaskId(task.task_id)}
            >
              查看 {task.task_type}
            </button>
          ))}
        </div>
        {selectedTaskId ? <TaskStatusPanel taskId={selectedTaskId} onSuccess={refreshTasks} /> : <p className="empty-state">暂无任务记录可查看。</p>}
      </PacketCard>

      <PacketCard title="取消任务" subtitle="POST /api/tasks/{task_id}/cancel 只改本地任务状态；不外联、不交易" status="local_cancel">
        <p>取消入口只面向 pending / running 任务，写入 local_task_cancel 调用血缘，并把步骤标记为 cancelled_by_user_no_external_call。</p>
        <p>不会调用 Tushare、DeepSeek 或 GitHub，不执行真实交易，不修改 strategy action。</p>
        <div className="button-row">
          {taskRecords.map((task) => {
            const cancellable = task.status === "pending" || task.status === "running";
            return (
              <button
                key={task.task_id}
                disabled={!cancellable}
                onClick={() => void cancelTask(task.task_id).then(() => refreshTasks())}
              >
                取消 {task.task_type}
              </button>
            );
          })}
        </div>
      </PacketCard>

      <PacketCard title="手动重试任务" subtitle="POST /api/tasks/{task_id}/retry 只创建新的本地 pending 任务；不自动外联、不交易" status="local_retry">
        <p>重试入口只面向 failed 且 retry_policy.manual_retry_eligible=true 的任务；点击后生成新的 task_id，原任务只追加本地审计日志。</p>
        <p>不会调用 Tushare、DeepSeek 或 GitHub，不执行真实交易，不修改 strategy action；新任务仍需后续按钮/worker 明确执行。</p>
        <div className="button-row">
          {taskRecords.map((task) => {
            const retryPolicy = (task.retry_policy ?? {}) as Record<string, unknown>;
            const retryable = task.status === "failed" && retryPolicy.manual_retry_eligible === true;
            return (
              <button
                key={task.task_id}
                disabled={!retryable}
                onClick={() => void retryTask(task.task_id).then(() => refreshTasks())}
              >
                重试 {task.task_type}
              </button>
            );
          })}
        </div>
      </PacketCard>

      <PacketCard title="原始目录 payload" subtitle="调试用 JSON；不含 token/key" status="safe">
        <JsonDetails title="task catalog raw" data={catalog} />
        <JsonDetails title="task status index raw" data={taskIndex ?? {}} />
        <JsonDetails title="task records raw" data={taskRecords} />
      </PacketCard>
    </>
  );
}
