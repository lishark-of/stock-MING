import { useEffect, useState } from "react";
import {
  getFactorValuesStorage,
  getSQLiteMetaStorage,
  getStorageCatalog,
  getStorageDataset,
  getStorageOverview,
  postStorageArtifactCleanupDryRun,
  postStoragePartitionMigrationDryRun,
  postStorageSchemaValidationDryRun,
  type TaskCreationEnvelope
} from "../api/client";
import DataLineageTable from "../components/DataLineageTable";
import JsonDetails from "../components/JsonDetails";
import MetricGrid from "../components/MetricGrid";
import PacketCard from "../components/PacketCard";
import StatusBadge from "../components/StatusBadge";
import TaskLaunchReceipt from "../components/TaskLaunchReceipt";
import TaskStatusPanel from "../components/TaskStatusPanel";

export default function StorageOverview() {
  const [overview, setOverview] = useState<Record<string, unknown>>({});
  const [cacheEnvelopeLedger, setCacheEnvelopeLedger] = useState<Array<Record<string, unknown>>>([]);
  const [cacheEnvelopeWarnings, setCacheEnvelopeWarnings] = useState<Array<string>>([]);
  const [storageCatalog, setStorageCatalog] = useState<Record<string, unknown>>({});
  const [catalogEnvelopeLedger, setCatalogEnvelopeLedger] = useState<Array<Record<string, unknown>>>([]);
  const [catalogEnvelopeWarnings, setCatalogEnvelopeWarnings] = useState<Array<string>>([]);
  const [factorValues, setFactorValues] = useState<Record<string, unknown>>({});
  const [sqliteMeta, setSqliteMeta] = useState<Record<string, unknown>>({});
  const [datasetDetails, setDatasetDetails] = useState<Record<string, Record<string, unknown>>>({});
  const [dryRunTaskId, setDryRunTaskId] = useState("");
  const [dryRunReceipt, setDryRunReceipt] = useState<TaskCreationEnvelope | null>(null);
  const [schemaValidationTaskId, setSchemaValidationTaskId] = useState("");
  const [schemaValidationReceipt, setSchemaValidationReceipt] = useState<TaskCreationEnvelope | null>(null);
  const [partitionDryRunTaskId, setPartitionDryRunTaskId] = useState("");
  const [partitionDryRunReceipt, setPartitionDryRunReceipt] = useState<TaskCreationEnvelope | null>(null);

  const refreshStorage = () => {
    void getStorageOverview().then((res) => {
      setOverview(res.data);
      setCacheEnvelopeLedger(res.call_ledger ?? []);
      setCacheEnvelopeWarnings(res.warnings ?? []);
    });
    void getStorageCatalog().then((res) => {
      setStorageCatalog(res.data);
      setCatalogEnvelopeLedger(res.call_ledger ?? []);
      setCatalogEnvelopeWarnings(res.warnings ?? []);
    });
    void getFactorValuesStorage().then((res) => setFactorValues(res.data));
    void getSQLiteMetaStorage().then((res) => setSqliteMeta(res.data));
    void Promise.all(["daily", "daily-basic", "moneyflow", "trade-cal", "backtest-results"].map((dataset) => getStorageDataset(dataset).then((res) => [dataset, res.data] as const))).then((items) =>
      setDatasetDetails(Object.fromEntries(items))
    );
  };
  const launchArtifactCleanupDryRun = () =>
    void postStorageArtifactCleanupDryRun({ source: "storage_overview_button" }).then((res) => {
      setDryRunReceipt(res);
      if (res.ok) setDryRunTaskId(res.data.task_id);
    });
  const launchSchemaValidationDryRun = () =>
    void postStorageSchemaValidationDryRun({ source: "storage_overview_button" }).then((res) => {
      setSchemaValidationReceipt(res);
      if (res.ok) setSchemaValidationTaskId(res.data.task_id);
    });
  const launchPartitionMigrationDryRun = () =>
    void postStoragePartitionMigrationDryRun({ source: "storage_overview_button" }).then((res) => {
      setPartitionDryRunReceipt(res);
      if (res.ok) setPartitionDryRunTaskId(res.data.task_id);
    });

  useEffect(() => {
    refreshStorage();
  }, []);

  const datasetStatus = overview.dataset_status as Record<string, unknown> | undefined;
  const datasetImplementation =
    (overview.dataset_implementation_status as Record<string, unknown> | undefined) ??
    (storageCatalog.dataset_implementation_status as Record<string, unknown> | undefined) ??
    {};
  const datasets = overview.datasets as Array<Record<string, unknown>> | undefined;
  const datasetCatalog =
    (storageCatalog.dataset_catalog as Array<Record<string, unknown>> | undefined) ??
    (overview.dataset_catalog as Array<Record<string, unknown>> | undefined);
  const datasetCards = [
    { key: "factor_values", label: "factor_values", packet: factorValues },
    { key: "daily", label: "daily", packet: datasetDetails.daily ?? {} },
    { key: "daily_basic", label: "daily_basic", packet: datasetDetails["daily-basic"] ?? {} },
    { key: "moneyflow", label: "moneyflow", packet: datasetDetails.moneyflow ?? {} },
    { key: "trade_cal", label: "trade_cal", packet: datasetDetails["trade-cal"] ?? {} },
    { key: "backtest_results", label: "backtest_results", packet: datasetDetails["backtest-results"] ?? {} }
  ];
  const factorMetadata = factorValues.metadata as Record<string, unknown> | undefined;
  const factorQuery = factorValues.query as Record<string, unknown> | undefined;
  const factorRows = (factorQuery?.rows as Array<Record<string, unknown>> | undefined) ?? [];
  const packetMetadataRows = (sqliteMeta.packet_metadata as Array<Record<string, unknown>> | undefined) ?? [];
  const taskMetadataRows = (sqliteMeta.task_metadata as Array<Record<string, unknown>> | undefined) ?? [];
  const sqliteMetadataSourceRows = (sqliteMeta.metadata_source_rows as Array<Record<string, unknown>> | undefined) ?? [];
  const sqlitePacketStatusCounts = sqliteMeta.packet_status_counts as Record<string, unknown> | undefined;
  const sqliteTaskStatusCounts = sqliteMeta.task_status_counts as Record<string, unknown> | undefined;
  const artifactHygiene = (overview.artifact_hygiene as Record<string, unknown> | undefined) ?? (storageCatalog.artifact_hygiene as Record<string, unknown> | undefined) ?? {};
  const artifactRows = (artifactHygiene.rows as Array<Record<string, unknown>> | undefined) ?? [];
  const artifactPatternRows = ((artifactHygiene.git_excluded_patterns as Array<string> | undefined) ?? []).map((pattern, index) => ({ index: index + 1, pattern }));
  const schemaMigration =
    (overview.schema_migration_preflight as Record<string, unknown> | undefined) ??
    (storageCatalog.schema_migration_preflight as Record<string, unknown> | undefined) ??
    {};
  const datasetVersionPolicy =
    (overview.dataset_version_policy as Record<string, unknown> | undefined) ??
    (storageCatalog.dataset_version_policy as Record<string, unknown> | undefined) ??
    {};
  const datasetVersionRows =
    (overview.dataset_version_rows as Array<Record<string, unknown>> | undefined) ??
    ((storageCatalog.dataset_version_rows as Array<Record<string, unknown>> | undefined) ?? []);
  const datasetVersionStatusCounts =
    (overview.dataset_version_status_counts as Record<string, unknown> | undefined) ??
    ((storageCatalog.dataset_version_status_counts as Record<string, unknown> | undefined) ?? {});
  const schemaMigrationRows =
    (overview.schema_migration_rows as Array<Record<string, unknown>> | undefined) ??
    ((schemaMigration.rows as Array<Record<string, unknown>> | undefined) ?? []);
  const schemaMigrationStatusCounts =
    (overview.schema_migration_status_counts as Record<string, unknown> | undefined) ??
    ((schemaMigration.status_counts as Record<string, unknown> | undefined) ?? {});
  const implementationStateCounts = datasetImplementation.state_counts as Record<string, unknown> | undefined;
  const implementationParquetStatusCounts = datasetImplementation.parquet_status_counts as Record<string, unknown> | undefined;
  const implementationRows = (datasetImplementation.dataset_rows as Array<Record<string, unknown>> | undefined) ?? [];
  const payloadCallLedger = (overview.call_ledger as Array<Record<string, unknown>> | undefined) ?? [];
  const cacheCallLedger = cacheEnvelopeLedger.length ? cacheEnvelopeLedger : payloadCallLedger;
  const cacheWarnings = cacheEnvelopeWarnings.length ? cacheEnvelopeWarnings : ((overview.warnings as Array<string> | undefined) ?? []);
  const catalogPayloadCallLedger = (storageCatalog.call_ledger as Array<Record<string, unknown>> | undefined) ?? [];
  const catalogCallLedger = catalogEnvelopeLedger.length ? catalogEnvelopeLedger : catalogPayloadCallLedger;
  const catalogWarnings = catalogEnvelopeWarnings.length ? catalogEnvelopeWarnings : ((storageCatalog.warnings as Array<string> | undefined) ?? []);
  const warningRows = cacheWarnings.map((warning, index) => ({ index: index + 1, warning }));
  const catalogWarningRows = catalogWarnings.map((warning, index) => ({ index: index + 1, warning }));
  const previewRows = datasetCards.flatMap((item) => {
    const query = item.packet.query as Record<string, unknown> | undefined;
    const rows = (query?.rows as Array<Record<string, unknown>> | undefined) ?? [];
    return rows.slice(0, 5).map((row, index) => ({ dataset: item.label, sample_index: index + 1, ...row }));
  });
  const datasetCallLedgerRows = [
    ...datasetCards.flatMap((item) => ((item.packet.call_ledger as Array<Record<string, unknown>> | undefined) ?? []).map((row) => ({ dataset: item.label, ...row }))),
    ...((sqliteMeta.call_ledger as Array<Record<string, unknown>> | undefined) ?? []).map((row) => ({ dataset: "sqlite_meta", ...row }))
  ];

  return (
    <>
      <div className="page-head">
        <h1>存储层</h1>
        <StatusBadge label={String(overview.store ?? "parquet_duckdb")} tone="neutral" />
      </div>

      <MetricGrid
        items={[
          { label: "store", value: overview.store as string | undefined },
          { label: "dataset catalog", value: overview.dataset_count as number | undefined },
          { label: "local pipeline datasets", value: datasetImplementation.local_pipeline_dataset_count as number | undefined },
          { label: "future gated datasets", value: datasetImplementation.future_button_gated_dataset_count as number | undefined },
          { label: "parquet ready", value: datasetImplementation.parquet_ready_dataset_count as number | undefined },
          { label: "parquet missing", value: datasetImplementation.parquet_missing_dataset_count as number | undefined },
          { label: "Tushare capable datasets", value: datasetImplementation.tushare_capable_dataset_count as number | undefined },
          { label: "local compute datasets", value: datasetImplementation.local_compute_capable_dataset_count as number | undefined },
          { label: "cache only", value: overview.cache_only, tone: overview.cache_only === false ? "bad" : "good" },
          { label: "external calls", value: overview.external_calls_triggered === true ? "存在" : "无", tone: overview.external_calls_triggered === true ? "bad" : "good" },
          { label: "Tushare", value: overview.tushare_called === true ? "已调用" : "未调用", tone: overview.tushare_called === true ? "bad" : "good" },
          { label: "DeepSeek", value: overview.deepseek_called === true ? "已调用" : "未调用", tone: overview.deepseek_called === true ? "bad" : "good" },
          { label: "GitHub", value: overview.github_called === true ? "已调用" : "未调用", tone: overview.github_called === true ? "bad" : "good" },
          { label: "真实交易", value: overview.does_not_execute_trades === false ? "可能" : "禁止", tone: overview.does_not_execute_trades === false ? "bad" : "good" },
          { label: "修改 action", value: overview.does_not_modify_strategy_action === false ? "可能" : "不会", tone: overview.does_not_modify_strategy_action === false ? "bad" : "good" },
          { label: "cache envelope ledger", value: cacheCallLedger.length },
          { label: "cache warnings", value: cacheWarnings.length },
          { label: "catalog envelope ledger", value: catalogCallLedger.length },
          { label: "catalog warnings", value: catalogWarnings.length },
          { label: "factor_values", value: String(datasetStatus?.factor_values ?? "missing") },
          { label: "daily", value: String(datasetStatus?.daily ?? "missing") },
          { label: "daily_basic", value: String(datasetStatus?.daily_basic ?? "missing") },
          { label: "moneyflow", value: String(datasetStatus?.moneyflow ?? "missing") },
          { label: "trade_cal", value: String(datasetStatus?.trade_cal ?? "missing") },
          { label: "backtest_results", value: String(datasetStatus?.backtest_results ?? "missing") },
          { label: "sqlite meta", value: String(overview.metadata_status ?? sqliteMeta.status ?? "missing") },
          { label: "packets", value: overview.packet_metadata_count ?? sqliteMeta.packet_count ?? 0 },
          { label: "tasks", value: overview.task_metadata_count ?? sqliteMeta.task_count ?? 0 },
          { label: "artifact hygiene", value: String(artifactHygiene.status ?? overview.artifact_hygiene_status ?? "audit_ready") },
          { label: "local artifacts", value: artifactHygiene.present_artifact_count ?? overview.artifact_hygiene_present_count ?? 0 },
          { label: "artifact review", value: artifactHygiene.review_required_count ?? overview.artifact_hygiene_review_required_count ?? 0 },
          { label: "schema migration", value: String(schemaMigration.status ?? overview.schema_migration_preflight_status ?? "preflight") },
          { label: "dataset version", value: String(datasetVersionPolicy.status ?? "policy_ready") },
          { label: "declared versions", value: datasetVersionPolicy.target_version_declared_count ?? overview.dataset_version_declared_count ?? 0 },
          { label: "version validations", value: datasetVersionPolicy.physical_dataset_version_validated_count ?? overview.physical_dataset_version_validated_count ?? 0 },
          { label: "migration rows", value: schemaMigrationRows.length },
          { label: "migrations executed", value: schemaMigration.migration_executed_count ?? overview.schema_migration_executed_count ?? 0 },
          { label: "physical schema checks", value: schemaMigration.physical_validation_done_count ?? overview.physical_schema_validation_done_count ?? 0 }
        ]}
      />

      <div className="grid">
        <PacketCard title="Parquet / DuckDB Storage" subtitle="只读查看本地数据集状态；不会触发刷新任务" status="cache_only">
          <p>本页只调用 FastAPI storage cache API，不调用 Tushare、DeepSeek 或 GitHub。</p>
          <p>daily / daily_basic / moneyflow / trade_cal / factor_values / backtest_results 通过 DuckDB 查询本地 Parquet；无缓存时只显示 missing。</p>
          <p>does_not_execute_trades 与 does_not_modify_strategy_action 必须保持为 true。</p>
        </PacketCard>

        <PacketCard title="Factor Values" subtitle="runtime.factor_values 本地落盘状态" status={String(factorMetadata?.status ?? "missing")}>
          <p>row_count: {String(factorValues.row_count ?? factorQuery?.row_count ?? 0)}</p>
          <p>path: {String(factorValues.path ?? factorMetadata?.path ?? "--")}</p>
          <p>cache_only: {String(factorValues.cache_only ?? true)}</p>
        </PacketCard>

        <PacketCard title="SQLite Metadata" subtitle="packet/task 元数据；不返回 payload_json" status={String(sqliteMeta.status ?? overview.metadata_status ?? "missing")}>
          <p>path: {String(sqliteMeta.path ?? "--")}</p>
          <p>packet_count: {String(sqliteMeta.packet_count ?? overview.packet_metadata_count ?? 0)}</p>
          <p>task_count: {String(sqliteMeta.task_count ?? overview.task_metadata_count ?? 0)}</p>
          <p>does_not_return_payload_json: {String(sqliteMeta.does_not_return_payload_json ?? true)}</p>
        </PacketCard>
      </div>

      <PacketCard title="SQLite metadata 安全摘要" subtitle="只展示安全列、状态分布和来源行；不返回 payload_json" status="sqlite_meta_safety">
        <p>metadata_is_payload_only: {String(sqliteMeta.metadata_is_payload_only ?? false)}</p>
        <p>packet_status_counts: {JSON.stringify(sqlitePacketStatusCounts ?? {})}</p>
        <p>task_status_counts: {JSON.stringify(sqliteTaskStatusCounts ?? {})}</p>
        <p>metadata_safe_columns: {JSON.stringify(sqliteMeta.metadata_safe_columns ?? {})}</p>
        <DataLineageTable rows={sqliteMetadataSourceRows} />
      </PacketCard>

      <PacketCard title="Storage implementation status" subtitle="只读展示数据集落地状态；不会创建 Parquet、刷新 Tushare 或运行回测" status={String(datasetImplementation.status ?? "partial_migration")}>
        <p>local pipeline / future gated: {String(datasetImplementation.local_pipeline_dataset_count ?? 0)} / {String(datasetImplementation.future_button_gated_dataset_count ?? 0)}</p>
        <p>parquet ready / missing: {String(datasetImplementation.parquet_ready_dataset_count ?? 0)} / {String(datasetImplementation.parquet_missing_dataset_count ?? 0)}</p>
        <p>Tushare capable / local compute: {String(datasetImplementation.tushare_capable_dataset_count ?? 0)} / {String(datasetImplementation.local_compute_capable_dataset_count ?? 0)}</p>
        <p>all external refreshes button gated: {String(datasetImplementation.all_external_refreshes_button_gated ?? true)}</p>
        <p>does not modify action / execute trades: {String(datasetImplementation.all_datasets_do_not_modify_strategy_action ?? true)} / {String(datasetImplementation.all_datasets_do_not_execute_trades ?? true)}</p>
        <p>state_counts: {JSON.stringify(implementationStateCounts ?? {})}</p>
        <p>parquet_status_counts: {JSON.stringify(implementationParquetStatusCounts ?? {})}</p>
        <DataLineageTable rows={implementationRows} />
      </PacketCard>

      <PacketCard title="Dataset version policy" subtitle="只读版本策略矩阵；声明版本不等于物理版本已验收，不写 manifest" status={String(datasetVersionPolicy.status ?? "policy_ready")}>
        <p>mode: {String(datasetVersionPolicy.mode ?? "cache_only_read_only_policy")}</p>
        <p>version_policy: {String(datasetVersionPolicy.version_policy ?? "contract_only_manifest_write_requires_explicit_task")}</p>
        <p>manifest_path: {String(datasetVersionPolicy.version_manifest_path ?? "--")}</p>
        <p>declared / physical validated: {String(datasetVersionPolicy.target_version_declared_count ?? 0)} / {String(datasetVersionPolicy.physical_dataset_version_validated_count ?? 0)}</p>
        <p>manifest_written_on_get / cache_get_writes_files: {String(datasetVersionPolicy.manifest_written_on_get ?? false)} / {String(datasetVersionPolicy.cache_get_writes_files ?? false)}</p>
        <p>status_counts: {JSON.stringify(datasetVersionStatusCounts)}</p>
        <DataLineageTable rows={datasetVersionRows} />
      </PacketCard>

      <PacketCard title="Schema migration preflight" subtitle="schema/version 迁移预检；只读、不写 Parquet、不读 payload、不外联" status={String(schemaMigration.status ?? "preflight_ready")}>
        <p>mode: {String(schemaMigration.mode ?? "metadata_only_read_only_preflight")}</p>
        <p>contract ready / datasets: {String(schemaMigration.contract_ready_count ?? 0)} / {String(schemaMigration.dataset_count ?? 0)}</p>
        <p>physical validation done / migrations executed: {String(schemaMigration.physical_validation_done_count ?? 0)} / {String(schemaMigration.migration_executed_count ?? 0)}</p>
        <p>cache_get_writes_files / physical_validation_reads_payloads: {String(schemaMigration.cache_get_writes_files ?? false)} / {String(schemaMigration.physical_validation_reads_payloads ?? false)}</p>
        <p>manual_migration_task_required: {String(schemaMigration.manual_migration_task_required ?? true)}</p>
        <p>status_counts: {JSON.stringify(schemaMigrationStatusCounts)}</p>
        <div className="actions">
          <button onClick={launchSchemaValidationDryRun}>运行 schema validation dry-run</button>
          <button onClick={launchPartitionMigrationDryRun}>生成 partition migration dry-run</button>
        </div>
        <TaskLaunchReceipt receipt={schemaValidationReceipt} />
        <TaskStatusPanel taskId={schemaValidationTaskId} onSuccess={refreshStorage} />
        <TaskLaunchReceipt receipt={partitionDryRunReceipt} />
        <TaskStatusPanel taskId={partitionDryRunTaskId} onSuccess={refreshStorage} />
        <DataLineageTable rows={schemaMigrationRows} />
      </PacketCard>

      <PacketCard title="Local artifact hygiene" subtitle="路径级预检；只展示本地生成物边界，不删除、不读 payload、不外联" status={String(artifactHygiene.status ?? "audit_ready")}>
        <p>cleanup_policy: {String(artifactHygiene.cleanup_policy ?? "manual_only_no_delete_on_get")}</p>
        <p>cleanup_task_status: {String(artifactHygiene.cleanup_task_status ?? "dry_run_button_gated")}</p>
        <p>cleanup_dry_run_route: {String(artifactHygiene.cleanup_dry_run_route ?? "POST /api/storage/artifact-hygiene/dry-run")}</p>
        <p>delete_files_on_get / auto_cleanup_on_get: {String(artifactHygiene.delete_files_on_get ?? false)} / {String(artifactHygiene.auto_cleanup_on_get ?? false)}</p>
        <p>does_not_read_file_payloads / does_not_scan_secret_values: {String(artifactHygiene.does_not_read_file_payloads ?? true)} / {String(artifactHygiene.does_not_scan_secret_values ?? true)}</p>
        <div className="actions">
          <button onClick={launchArtifactCleanupDryRun}>生成 cleanup dry-run</button>
        </div>
        <TaskLaunchReceipt receipt={dryRunReceipt} />
        <TaskStatusPanel taskId={dryRunTaskId} onSuccess={refreshStorage} />
        <DataLineageTable rows={artifactRows} />
      </PacketCard>

      <PacketCard title="Generated artifact git guard" subtitle="push gate 使用这些边界阻止生成物、数据文件和本地缓存进入 git" status="artifact_guard">
        <p>tracked_artifact_gate: {String(artifactHygiene.tracked_artifact_gate ?? "scripts/push_gate_3_0.sh generated artifact scan")}</p>
        <p>data_files_allowed_in_git: {String(artifactHygiene.data_files_allowed_in_git ?? false)}</p>
        <DataLineageTable rows={artifactPatternRows} />
      </PacketCard>

      <PacketCard title="数据集明细" subtitle="GET /api/storage/{dataset} 只读查询本地 Parquet；不刷新数据" status="dataset_cache">
        <DataLineageTable
          rows={datasetCards.map((item) => {
            const metadata = item.packet.metadata as Record<string, unknown> | undefined;
            const query = item.packet.query as Record<string, unknown> | undefined;
            return {
              dataset: item.label,
              status: metadata?.status ?? item.packet.status ?? "missing",
              row_count: item.packet.row_count ?? query?.row_count ?? 0,
              path: item.packet.path ?? metadata?.path ?? query?.path ?? "--",
              cache_only: item.packet.cache_only ?? true,
              external_calls_triggered: item.packet.external_calls_triggered ?? false,
              tushare_called: item.packet.tushare_called ?? false,
              deepseek_called: item.packet.deepseek_called ?? false,
              github_called: item.packet.github_called ?? false
            };
          })}
        />
      </PacketCard>

      <PacketCard title="数据集目录" subtitle="数据集用途、别名、写入边界和未来任务归属；只读、不写 Parquet" status="dataset_catalog">
        <DataLineageTable rows={datasetCatalog ?? []} />
      </PacketCard>

      <PacketCard title="GET storage catalog envelope call_ledger" subtitle="GET /api/storage/catalog 顶层响应血缘；前端优先读取 res.call_ledger" status="lineage">
        <DataLineageTable rows={catalogCallLedger} />
      </PacketCard>

      <PacketCard title="GET storage catalog warnings" subtitle="独立数据集目录 API 提示；只读、不写 Parquet、不外联" status="warnings">
        <DataLineageTable rows={catalogWarningRows} />
      </PacketCard>

      <PacketCard title="GET storage envelope call_ledger" subtitle="GET /api/storage 顶层响应血缘；前端优先读取 res.call_ledger" status="lineage">
        <DataLineageTable rows={cacheCallLedger} />
      </PacketCard>

      <PacketCard title="数据集 call_ledger 汇总" subtitle="GET /api/storage/factor-values、daily、daily-basic、moneyflow、trade-cal、backtest-results、sqlite-meta 的本地读取血缘" status="lineage">
        <DataLineageTable rows={datasetCallLedgerRows} />
      </PacketCard>

      <PacketCard title="GET storage envelope warnings" subtitle="顶层响应提示；不包含 token/key/错误堆栈" status="warnings">
        <DataLineageTable rows={warningRows} />
      </PacketCard>

      <PacketCard title="数据集状态" subtitle="本地 Parquet 数据集元数据" status="overview">
        <DataLineageTable rows={datasets ?? []} />
      </PacketCard>

      <PacketCard title="factor_values 样例" subtitle="只展示安全标量；不含 token/key" status="preview">
        <DataLineageTable rows={factorRows} />
      </PacketCard>

      <PacketCard title="SQLite packet metadata" subtitle="只展示 packet_key/status/mode/updated_at/payload_bytes，不展示 payload_json" status="sqlite_meta">
        <DataLineageTable rows={packetMetadataRows} />
      </PacketCard>

      <PacketCard title="SQLite task metadata" subtitle="只展示 task_id/status/current_step/output_packet_key，不展示 payload_json" status="sqlite_meta">
        <DataLineageTable rows={taskMetadataRows} />
      </PacketCard>

      <PacketCard title="daily / daily_basic / moneyflow / trade_cal / backtest_results 样例" subtitle="只读本地 Parquet 样例；无缓存时为空表" status="preview">
        <DataLineageTable rows={previewRows} />
      </PacketCard>

      <PacketCard title="原始 storage payload" subtitle="调试用 JSON；cache API 永不外联" status="safe">
        <JsonDetails title="storage overview raw" data={overview} />
        <JsonDetails title="storage catalog raw" data={storageCatalog} />
        <JsonDetails title="artifact hygiene raw" data={artifactHygiene} />
        <JsonDetails title="factor values raw" data={factorValues} />
        <JsonDetails title="sqlite meta raw" data={sqliteMeta} />
        <JsonDetails title="daily raw" data={datasetDetails.daily ?? {}} />
        <JsonDetails title="daily_basic raw" data={datasetDetails["daily-basic"] ?? {}} />
        <JsonDetails title="moneyflow raw" data={datasetDetails.moneyflow ?? {}} />
        <JsonDetails title="trade_cal raw" data={datasetDetails["trade-cal"] ?? {}} />
        <JsonDetails title="backtest_results raw" data={datasetDetails["backtest-results"] ?? {}} />
      </PacketCard>
    </>
  );
}
