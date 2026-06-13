import { useEffect, useState } from "react";
import {
  getFactorValuesStorage,
  getSQLiteMetaStorage,
  getStorageCatalog,
  getStorageDataset,
  getStorageOverview,
  postStorageArtifactCleanupDryRun,
  postStorageCacheTtlDryRun,
  postStorageCompactionDryRun,
  postStorageDatasetVersionManifestDryRun,
  postStorageDatasetVersionManifestReview,
  postStorageDatasetVersionManifestValidate,
  postStorageDatasetVersionManifestWrite,
  postStoragePartitionMigrationDryRun,
  postStorageSchemaValidationAcceptance,
  postStorageSchemaValidationDryRun,
  type StorageQueryParams,
  type TaskCreationEnvelope
} from "../api/client";
import DataLineageTable from "../components/DataLineageTable";
import JsonDetails from "../components/JsonDetails";
import MetricGrid from "../components/MetricGrid";
import PacketCard from "../components/PacketCard";
import StatusBadge from "../components/StatusBadge";
import TaskLaunchReceipt from "../components/TaskLaunchReceipt";
import TaskStatusPanel from "../components/TaskStatusPanel";

const STORAGE_DATASET_ENDPOINTS = ["daily", "daily-basic", "moneyflow", "trade-cal", "backtest-results"];

type StorageFilterDraft = {
  limit: string;
  ts_code: string;
  trade_date: string;
  start_date: string;
  end_date: string;
};

function storageCursor(value: unknown): string {
  return String(value ?? "").trim();
}

function defaultStorageFilterDraft(): StorageFilterDraft {
  return {
    limit: "100",
    ts_code: "",
    trade_date: "",
    start_date: "",
    end_date: ""
  };
}

function storageFilterDraft(value: StorageFilterDraft | undefined): StorageFilterDraft {
  return { ...defaultStorageFilterDraft(), ...(value ?? {}) };
}

function storageQueryParamsFromDraft(draft: StorageFilterDraft | undefined, cursor = ""): StorageQueryParams {
  const filters = storageFilterDraft(draft);
  const params: StorageQueryParams = {};
  const safeLimit = Number.parseInt(filters.limit, 10);
  if (Number.isFinite(safeLimit) && safeLimit > 0) params.limit = safeLimit;
  const safeCursor = storageCursor(cursor);
  if (safeCursor) params.cursor = safeCursor;
  for (const key of ["ts_code", "trade_date", "start_date", "end_date"] as const) {
    const value = filters[key].trim();
    if (value) params[key] = value;
  }
  return params;
}

export default function StorageOverview() {
  const [overview, setOverview] = useState<Record<string, unknown>>({});
  const [cacheEnvelopeLedger, setCacheEnvelopeLedger] = useState<Array<Record<string, unknown>>>([]);
  const [cacheEnvelopeWarnings, setCacheEnvelopeWarnings] = useState<Array<string>>([]);
  const [storageCatalog, setStorageCatalog] = useState<Record<string, unknown>>({});
  const [catalogEnvelopeLedger, setCatalogEnvelopeLedger] = useState<Array<Record<string, unknown>>>([]);
  const [catalogEnvelopeWarnings, setCatalogEnvelopeWarnings] = useState<Array<string>>([]);
  const [datasetCursors, setDatasetCursors] = useState<Record<string, string>>({});
  const [datasetFilters, setDatasetFilters] = useState<Record<string, StorageFilterDraft>>({});
  const [factorValues, setFactorValues] = useState<Record<string, unknown>>({});
  const [sqliteMeta, setSqliteMeta] = useState<Record<string, unknown>>({});
  const [datasetDetails, setDatasetDetails] = useState<Record<string, Record<string, unknown>>>({});
  const [dryRunTaskId, setDryRunTaskId] = useState("");
  const [dryRunReceipt, setDryRunReceipt] = useState<TaskCreationEnvelope | null>(null);
  const [schemaValidationTaskId, setSchemaValidationTaskId] = useState("");
  const [schemaValidationReceipt, setSchemaValidationReceipt] = useState<TaskCreationEnvelope | null>(null);
  const [schemaAcceptanceTaskId, setSchemaAcceptanceTaskId] = useState("");
  const [schemaAcceptanceReceipt, setSchemaAcceptanceReceipt] = useState<TaskCreationEnvelope | null>(null);
  const [manifestDryRunTaskId, setManifestDryRunTaskId] = useState("");
  const [manifestDryRunReceipt, setManifestDryRunReceipt] = useState<TaskCreationEnvelope | null>(null);
  const [manifestReviewTaskId, setManifestReviewTaskId] = useState("");
  const [manifestReviewReceipt, setManifestReviewReceipt] = useState<TaskCreationEnvelope | null>(null);
  const [manifestWriteTaskId, setManifestWriteTaskId] = useState("");
  const [manifestWriteReceipt, setManifestWriteReceipt] = useState<TaskCreationEnvelope | null>(null);
  const [manifestValidateTaskId, setManifestValidateTaskId] = useState("");
  const [manifestValidateReceipt, setManifestValidateReceipt] = useState<TaskCreationEnvelope | null>(null);
  const [partitionDryRunTaskId, setPartitionDryRunTaskId] = useState("");
  const [partitionDryRunReceipt, setPartitionDryRunReceipt] = useState<TaskCreationEnvelope | null>(null);
  const [compactionDryRunTaskId, setCompactionDryRunTaskId] = useState("");
  const [compactionDryRunReceipt, setCompactionDryRunReceipt] = useState<TaskCreationEnvelope | null>(null);
  const [cacheTtlDryRunTaskId, setCacheTtlDryRunTaskId] = useState("");
  const [cacheTtlDryRunReceipt, setCacheTtlDryRunReceipt] = useState<TaskCreationEnvelope | null>(null);

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
    void getFactorValuesStorage(storageQueryParamsFromDraft(datasetFilters.factor_values, datasetCursors.factor_values)).then((res) => setFactorValues(res.data));
    void getSQLiteMetaStorage().then((res) => setSqliteMeta(res.data));
    void Promise.all(STORAGE_DATASET_ENDPOINTS.map((dataset) => getStorageDataset(dataset, storageQueryParamsFromDraft(datasetFilters[dataset], datasetCursors[dataset])).then((res) => [dataset, res.data] as const))).then((items) =>
      setDatasetDetails(Object.fromEntries(items))
    );
  };
  const loadStorageDatasetPage = (cursorKey: string, dataset: string, cursor = "", filterOverride?: StorageFilterDraft) => {
    const nextCursor = storageCursor(cursor);
    const queryParams = storageQueryParamsFromDraft(filterOverride ?? datasetFilters[cursorKey], nextCursor);
    setDatasetCursors((prev) => ({ ...prev, [cursorKey]: nextCursor }));
    if (cursorKey === "factor_values") {
      void getFactorValuesStorage(queryParams).then((res) => setFactorValues(res.data));
      return;
    }
    void getStorageDataset(dataset, queryParams).then((res) => {
      setDatasetDetails((prev) => ({ ...prev, [dataset]: res.data }));
    });
  };
  const updateStorageDatasetFilter = (cursorKey: string, key: keyof StorageFilterDraft, value: string) => {
    setDatasetFilters((prev) => ({
      ...prev,
      [cursorKey]: {
        ...storageFilterDraft(prev[cursorKey]),
        [key]: value
      }
    }));
  };
  const resetStorageDatasetFilters = (cursorKey: string, dataset: string) => {
    const defaults = defaultStorageFilterDraft();
    setDatasetFilters((prev) => ({ ...prev, [cursorKey]: defaults }));
    loadStorageDatasetPage(cursorKey, dataset, "", defaults);
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
  const launchSchemaValidationAcceptance = () =>
    void postStorageSchemaValidationAcceptance({ source: "storage_overview_button" }).then((res) => {
      setSchemaAcceptanceReceipt(res);
      if (res.ok) setSchemaAcceptanceTaskId(res.data.task_id);
    });
  const launchManifestDryRun = () =>
    void postStorageDatasetVersionManifestDryRun({ source: "storage_overview_button" }).then((res) => {
      setManifestDryRunReceipt(res);
      if (res.ok) setManifestDryRunTaskId(res.data.task_id);
    });
  const launchManifestReview = () =>
    void postStorageDatasetVersionManifestReview({ source: "storage_overview_button" }).then((res) => {
      setManifestReviewReceipt(res);
      if (res.ok) setManifestReviewTaskId(res.data.task_id);
    });
  const launchManifestWrite = () =>
    void postStorageDatasetVersionManifestWrite({ source: "storage_overview_button", confirm_manifest_write: true }).then((res) => {
      setManifestWriteReceipt(res);
      if (res.ok) setManifestWriteTaskId(res.data.task_id);
    });
  const launchManifestValidate = () =>
    void postStorageDatasetVersionManifestValidate({ source: "storage_overview_button" }).then((res) => {
      setManifestValidateReceipt(res);
      if (res.ok) setManifestValidateTaskId(res.data.task_id);
    });
  const launchPartitionMigrationDryRun = () =>
    void postStoragePartitionMigrationDryRun({ source: "storage_overview_button" }).then((res) => {
      setPartitionDryRunReceipt(res);
      if (res.ok) setPartitionDryRunTaskId(res.data.task_id);
    });
  const launchCompactionDryRun = () =>
    void postStorageCompactionDryRun({ source: "storage_overview_button" }).then((res) => {
      setCompactionDryRunReceipt(res);
      if (res.ok) setCompactionDryRunTaskId(res.data.task_id);
    });
  const launchCacheTtlDryRun = () =>
    void postStorageCacheTtlDryRun({ source: "storage_overview_button" }).then((res) => {
      setCacheTtlDryRunReceipt(res);
      if (res.ok) setCacheTtlDryRunTaskId(res.data.task_id);
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
    { key: "factor_values", cursorKey: "factor_values", endpoint: "factor-values", label: "factor_values", packet: factorValues },
    { key: "daily", cursorKey: "daily", endpoint: "daily", label: "daily", packet: datasetDetails.daily ?? {} },
    { key: "daily_basic", cursorKey: "daily-basic", endpoint: "daily-basic", label: "daily_basic", packet: datasetDetails["daily-basic"] ?? {} },
    { key: "moneyflow", cursorKey: "moneyflow", endpoint: "moneyflow", label: "moneyflow", packet: datasetDetails.moneyflow ?? {} },
    { key: "trade_cal", cursorKey: "trade-cal", endpoint: "trade-cal", label: "trade_cal", packet: datasetDetails["trade-cal"] ?? {} },
    { key: "backtest_results", cursorKey: "backtest-results", endpoint: "backtest-results", label: "backtest_results", packet: datasetDetails["backtest-results"] ?? {} }
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
  const artifactCleanupReview =
    (overview.artifact_cleanup_review_contract as Record<string, unknown> | undefined) ??
    ((artifactHygiene.artifact_cleanup_review_contract as Record<string, unknown> | undefined) ??
      ((storageCatalog.artifact_cleanup_review_contract as Record<string, unknown> | undefined) ?? {}));
  const artifactCleanupReviewRows =
    (overview.artifact_cleanup_review_rows as Array<Record<string, unknown>> | undefined) ??
    ((artifactHygiene.artifact_cleanup_review_rows as Array<Record<string, unknown>> | undefined) ??
      ((artifactCleanupReview.rows as Array<Record<string, unknown>> | undefined) ?? []));
  const schemaMigration =
    (overview.schema_migration_preflight as Record<string, unknown> | undefined) ??
    (storageCatalog.schema_migration_preflight as Record<string, unknown> | undefined) ??
    {};
  const datasetVersionPolicy =
    (overview.dataset_version_policy as Record<string, unknown> | undefined) ??
    (storageCatalog.dataset_version_policy as Record<string, unknown> | undefined) ??
    {};
  const datasetVersionManifestEvidence =
    (overview.dataset_version_manifest_evidence_audit as Record<string, unknown> | undefined) ??
    (storageCatalog.dataset_version_manifest_evidence_audit as Record<string, unknown> | undefined) ??
    {};
  const datasetVersionRows =
    (overview.dataset_version_rows as Array<Record<string, unknown>> | undefined) ??
    ((storageCatalog.dataset_version_rows as Array<Record<string, unknown>> | undefined) ?? []);
  const datasetVersionManifestEvidenceRows =
    (overview.dataset_version_manifest_evidence_rows as Array<Record<string, unknown>> | undefined) ??
    ((storageCatalog.dataset_version_manifest_evidence_rows as Array<Record<string, unknown>> | undefined) ?? []);
  const datasetVersionStatusCounts =
    (overview.dataset_version_status_counts as Record<string, unknown> | undefined) ??
    ((storageCatalog.dataset_version_status_counts as Record<string, unknown> | undefined) ?? {});
  const datasetVersionManifestEvidenceStatusCounts =
    (overview.dataset_version_manifest_evidence_status_counts as Record<string, unknown> | undefined) ??
    ((storageCatalog.dataset_version_manifest_evidence_status_counts as Record<string, unknown> | undefined) ?? {});
  const schemaMigrationRows =
    (overview.schema_migration_rows as Array<Record<string, unknown>> | undefined) ??
    ((schemaMigration.rows as Array<Record<string, unknown>> | undefined) ?? []);
  const schemaMigrationStatusCounts =
    (overview.schema_migration_status_counts as Record<string, unknown> | undefined) ??
    ((schemaMigration.status_counts as Record<string, unknown> | undefined) ?? {});
  const duckdbQueryService = (overview.duckdb_query_service as Record<string, unknown> | undefined) ?? {};
  const duckdbQueryRows =
    (overview.duckdb_query_service_rows as Array<Record<string, unknown>> | undefined) ??
    ((duckdbQueryService.rows as Array<Record<string, unknown>> | undefined) ?? []);
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
  const queryResultContractRows = datasetCards.map((item) => {
    const contract = item.packet.query_result_contract as Record<string, unknown> | undefined;
    return {
      dataset: item.label,
      schema_version: contract?.schema_version ?? "duckdb_query_result_contract.v1",
      row_count: contract?.row_count ?? item.packet.row_count ?? 0,
      projected_columns: JSON.stringify(contract?.projected_columns ?? item.packet.projected_columns ?? []),
      missing_projected_columns: JSON.stringify(contract?.missing_projected_columns ?? item.packet.missing_projected_columns ?? []),
      has_more: contract?.has_more ?? false,
      next_cursor: contract?.next_cursor ?? "",
      external_calls_triggered: contract?.external_calls_triggered ?? false
    };
  });
  const queryPageRows = datasetCards.map((item) => {
    const pageInfo = item.packet.page_info as Record<string, unknown> | undefined;
    return {
      dataset: item.label,
      limit: pageInfo?.limit ?? 100,
      cursor: pageInfo?.cursor ?? "",
      cursor_status: pageInfo?.cursor_status ?? "not_provided",
      offset: pageInfo?.offset ?? 0,
      has_more: pageInfo?.has_more ?? false,
      next_cursor: pageInfo?.next_cursor ?? "",
      returned_row_count: pageInfo?.returned_row_count ?? item.packet.row_count ?? 0
    };
  });
  const cursorControlRows = datasetCards.map((item) => {
    const pageInfo = item.packet.page_info as Record<string, unknown> | undefined;
    const contract = item.packet.query_result_contract as Record<string, unknown> | undefined;
    const nextCursor = storageCursor(pageInfo?.next_cursor ?? contract?.next_cursor);
    return {
      dataset: item.label,
      endpoint: item.endpoint,
      current_ui_cursor: datasetCursors[item.cursorKey] ?? "",
      returned_cursor: pageInfo?.cursor ?? "",
      cursor_status: pageInfo?.cursor_status ?? "not_provided",
      has_more: pageInfo?.has_more ?? contract?.has_more ?? false,
      next_cursor: nextCursor,
      can_load_next: Boolean(nextCursor),
      read_only_get_cursor: true,
      external_calls_triggered: item.packet.external_calls_triggered ?? false
    };
  });
  const datasetFilterRows = datasetCards.map((item) => {
    const filters = storageFilterDraft(datasetFilters[item.cursorKey]);
    const query = item.packet.query as Record<string, unknown> | undefined;
    return {
      dataset: item.label,
      endpoint: item.endpoint,
      limit: filters.limit,
      ts_code: filters.ts_code,
      trade_date: filters.trade_date,
      start_date: filters.start_date,
      end_date: filters.end_date,
      applied_filters: JSON.stringify(query?.applied_filters ?? item.packet.applied_filters ?? []),
      skipped_filters: JSON.stringify(query?.skipped_filters ?? item.packet.skipped_filters ?? []),
      filter_policy: "read_only_get_query_params_v1",
      external_calls_triggered: item.packet.external_calls_triggered ?? false
    };
  });
  const datasetCallLedgerRows = [
    ...datasetCards.flatMap((item) => ((item.packet.call_ledger as Array<Record<string, unknown>> | undefined) ?? []).map((row) => ({ dataset: item.label, ...row }))),
    ...((sqliteMeta.call_ledger as Array<Record<string, unknown>> | undefined) ?? []).map((row) => ({ dataset: "sqlite_meta", ...row }))
  ];
  const productionReadiness = (overview.production_readiness as Record<string, unknown> | undefined) ?? {};
  const storageProductionBlockerAudit =
    (overview.storage_production_blocker_audit as Record<string, unknown> | undefined) ??
    ((storageCatalog.storage_production_blocker_audit as Record<string, unknown> | undefined) ?? {});
  const storageProductionBlockerRows =
    (overview.storage_production_blocker_rows as Array<Record<string, unknown>> | undefined) ??
    ((storageCatalog.storage_production_blocker_rows as Array<Record<string, unknown>> | undefined) ?? []);
  const storageProductionReadinessReceipt =
    (overview.storage_production_readiness_receipt as Record<string, unknown> | undefined) ??
    ((storageCatalog.storage_production_readiness_receipt as Record<string, unknown> | undefined) ?? {});
  const storageProductionReadinessReceiptRows =
    (overview.storage_production_readiness_receipt_rows as Array<Record<string, unknown>> | undefined) ??
    ((storageCatalog.storage_production_readiness_receipt_rows as Array<Record<string, unknown>> | undefined) ?? []);
  const storagePhysicalMigrationActivationReceipt =
    (overview.storage_physical_migration_activation_receipt as Record<string, unknown> | undefined) ??
    ((storageCatalog.storage_physical_migration_activation_receipt as Record<string, unknown> | undefined) ?? {});
  const storagePhysicalMigrationActivationRows =
    (overview.storage_physical_migration_activation_rows as Array<Record<string, unknown>> | undefined) ??
    ((storageCatalog.storage_physical_migration_activation_rows as Array<Record<string, unknown>> | undefined) ?? []);

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
          { label: "cleanup review", value: String(artifactCleanupReview.status ?? overview.artifact_cleanup_review_status ?? "manual_review_ready_no_candidates") },
          { label: "delete executed", value: overview.artifact_cleanup_delete_executed_count ?? artifactCleanupReview.delete_executed_count ?? 0, tone: Number(overview.artifact_cleanup_delete_executed_count ?? artifactCleanupReview.delete_executed_count ?? 0) > 0 ? "bad" : "good" },
          { label: "delete command", value: artifactCleanupReview.safe_delete_command_generated === true ? "generated" : "not generated", tone: artifactCleanupReview.safe_delete_command_generated === true ? "bad" : "good" },
          { label: "schema migration", value: String(schemaMigration.status ?? overview.schema_migration_preflight_status ?? "preflight") },
          { label: "dataset version", value: String(datasetVersionPolicy.status ?? "policy_ready") },
          { label: "DuckDB query service", value: String(duckdbQueryService.status ?? overview.duckdb_query_service_status ?? "service_ready") },
          { label: "DuckDB max limit", value: duckdbQueryService.max_limit ?? overview.duckdb_query_max_limit ?? 0 },
          { label: "storage production", value: storageProductionBlockerAudit.status as string | undefined, tone: storageProductionBlockerAudit.production_storage_complete === true ? "good" : "warn" },
          { label: "storage blockers", value: overview.storage_production_blocker_count ?? storageProductionBlockerAudit.blocking_criterion_count ?? 0, tone: Number(overview.storage_production_blocker_count ?? storageProductionBlockerAudit.blocking_criterion_count ?? 0) > 0 ? "warn" : "good" },
          { label: "storage receipt", value: String(storageProductionReadinessReceipt.status ?? overview.storage_production_readiness_receipt_status ?? "missing"), tone: storageProductionReadinessReceipt.local_receipt_ready === true ? "good" : "warn" },
          { label: "receipt blocked", value: storageProductionReadinessReceipt.blocked_readiness_count ?? 0, tone: Number(storageProductionReadinessReceipt.blocked_readiness_count ?? 0) > 0 ? "warn" : "good" },
          { label: "storage activation", value: String(storagePhysicalMigrationActivationReceipt.status ?? overview.storage_physical_migration_activation_status ?? "missing"), tone: storagePhysicalMigrationActivationReceipt.local_activation_receipt_ready === true ? "good" : "warn" },
          { label: "activation blockers", value: storagePhysicalMigrationActivationReceipt.blocked_activation_count ?? 0, tone: Number(storagePhysicalMigrationActivationReceipt.blocked_activation_count ?? 0) > 0 ? "warn" : "good" },
          { label: "physical schema done", value: String(storagePhysicalMigrationActivationReceipt.physical_schema_validation_done ?? false), tone: storagePhysicalMigrationActivationReceipt.physical_schema_validation_done === true ? "good" : "warn" },
          { label: "declared versions", value: datasetVersionPolicy.target_version_declared_count ?? overview.dataset_version_declared_count ?? 0 },
          { label: "version validations", value: datasetVersionPolicy.physical_dataset_version_validated_count ?? overview.physical_dataset_version_validated_count ?? 0 },
          { label: "manifest evidence", value: String(datasetVersionManifestEvidence.status ?? overview.dataset_version_manifest_evidence_status ?? "manifest_missing_validation_pending") },
          { label: "manifest validated", value: datasetVersionManifestEvidence.validated_dataset_count ?? overview.dataset_version_manifest_evidence_validated_count ?? 0 },
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

      <PacketCard title="DuckDB query service policy" subtitle="所有数据集查询走 FastAPI + DuckDB wrapper；前端不直接读 DataFrame、不写 Parquet" status={String(duckdbQueryService.status ?? "service_ready")}>
        <p>query_wrapper: {String(duckdbQueryService.query_wrapper ?? overview.duckdb_query_wrapper ?? "duckdb_filtered_parquet.v1")}</p>
        <p>supported_filter_params: {JSON.stringify(duckdbQueryService.supported_filter_params ?? ["limit", "cursor", "ts_code", "trade_date", "start_date", "end_date"])}</p>
        <p>default_limit / max_limit: {String(duckdbQueryService.default_limit ?? 100)} / {String(duckdbQueryService.max_limit ?? overview.duckdb_query_max_limit ?? 10000)}</p>
        <p>safe_parameter_binding / safe_limit_enforced: {String(duckdbQueryService.safe_parameter_binding ?? true)} / {String(duckdbQueryService.safe_limit_enforced ?? true)}</p>
        <p>typed_projection / cursor_pagination / query_result_contract: {String(duckdbQueryService.typed_projection_enabled ?? true)} / {String(duckdbQueryService.cursor_pagination_enabled ?? true)} / {String(duckdbQueryService.query_result_contract_enabled ?? true)}</p>
        <p>frontend_executes_query / cache_get_writes_files: {String(duckdbQueryService.frontend_executes_query ?? false)} / {String(duckdbQueryService.cache_get_writes_files ?? false)}</p>
        <DataLineageTable rows={duckdbQueryRows} />
      </PacketCard>

      <PacketCard title="Storage production blocker audit" subtitle="storage_production_blocker_audit：LTG-05 生产化阻断项，不把 dry-run / preflight 误称为完成" status={String(storageProductionBlockerAudit.status ?? "missing")}>
        <p>schema_version: {String(storageProductionBlockerAudit.schema_version ?? "command_center_3_storage_production_blocker_audit.v1")}</p>
        <p>scope: {String(storageProductionBlockerAudit.scope ?? "ltg_05_storage_duckdb_parquet_productionization")}</p>
        <p>production_storage_complete: {String(storageProductionBlockerAudit.production_storage_complete ?? false)}</p>
        <p>dry_runs_are_not_production_completion: {String(storageProductionBlockerAudit.dry_runs_are_not_production_completion ?? true)}</p>
        <p>preflight_is_not_physical_migration: {String(storageProductionBlockerAudit.preflight_is_not_physical_migration ?? true)}</p>
        <p>dataset_version_policy_is_not_manifest_validation: {String(storageProductionBlockerAudit.dataset_version_policy_is_not_manifest_validation ?? true)}</p>
      </PacketCard>

      <PacketCard title="Storage production blocker rows" subtitle="schema、version、partition、compaction、TTL refresh 与 query service 的生产缺口" status="storage_production_blocker_rows">
        <DataLineageTable rows={storageProductionBlockerRows} />
      </PacketCard>

      <PacketCard title="Storage production readiness receipt" subtitle="LTG-05 下一步收据；允许显式 POST 审阅任务，不允许 GET 迁移、自动刷新或把收据当生产完成" status={String(storageProductionReadinessReceipt.status ?? "missing")}>
        <p>schema_version: {String(storageProductionReadinessReceipt.schema_version ?? "command_center_3_storage_production_readiness_receipt.v1")}</p>
        <p>scope: {String(storageProductionReadinessReceipt.scope ?? "local_storage_production_readiness_receipt_no_physical_migration")}</p>
        <p>local_receipt_ready: {String(storageProductionReadinessReceipt.local_receipt_ready ?? false)}</p>
        <p>allowed_next_step: {String(storageProductionReadinessReceipt.allowed_next_step ?? "explicit_post_task_storage_schema_acceptance_manifest_review")}</p>
        <p>production_storage_complete: {String(storageProductionReadinessReceipt.production_storage_complete ?? false)}</p>
        <p>provider_refresh_called_by_receipt / cache_get_external_calls: {String(storageProductionReadinessReceipt.provider_refresh_called_by_receipt ?? false)} / {String(storageProductionReadinessReceipt.cache_get_external_calls ?? false)}</p>
        <p>tushare / deepseek / github: {String(storageProductionReadinessReceipt.tushare_called_by_receipt ?? false)} / {String(storageProductionReadinessReceipt.deepseek_called ?? false)} / {String(storageProductionReadinessReceipt.github_called ?? false)}</p>
        <p>not_allowed_next_steps: {JSON.stringify(storageProductionReadinessReceipt.not_allowed_next_steps ?? ["GET /api/storage physical migration", "GET /api/storage provider refresh", "dry-run/preflight/receipt as production storage completion"])}</p>
        <DataLineageTable rows={storageProductionReadinessReceiptRows} />
      </PacketCard>

      <PacketCard title="Storage physical migration activation receipt" subtitle="LTG-05 物理迁移激活收据；只列出显式执行前置条件，不写 Parquet、不刷新 provider、不删除文件" status={String(storagePhysicalMigrationActivationReceipt.status ?? "missing")}>
        <p>schema_version: {String(storagePhysicalMigrationActivationReceipt.schema_version ?? "command_center_3_storage_physical_migration_activation_receipt.v1")}</p>
        <p>scope: {String(storagePhysicalMigrationActivationReceipt.scope ?? "local_storage_physical_migration_activation_receipt_no_physical_execution")}</p>
        <p>local_activation_receipt_ready: {String(storagePhysicalMigrationActivationReceipt.local_activation_receipt_ready ?? false)}</p>
        <p>allowed_next_step: {String(storagePhysicalMigrationActivationReceipt.allowed_next_step ?? "explicit_schema_acceptance_manifest_validate_then_partition_compaction_ttl_cleanup_reviews")}</p>
        <p>production_storage_complete / physical_schema_validation_done: {String(storagePhysicalMigrationActivationReceipt.production_storage_complete ?? false)} / {String(storagePhysicalMigrationActivationReceipt.physical_schema_validation_done ?? false)}</p>
        <p>parquet_written / manifest_written / cleanup_delete_generated: {String(storagePhysicalMigrationActivationReceipt.parquet_written_by_receipt ?? false)} / {String(storagePhysicalMigrationActivationReceipt.manifest_written_by_receipt ?? false)} / {String(storagePhysicalMigrationActivationReceipt.cleanup_delete_generated_by_receipt ?? false)}</p>
        <p>provider_refresh / cache_get_external_calls: {String(storagePhysicalMigrationActivationReceipt.provider_refresh_called_by_receipt ?? false)} / {String(storagePhysicalMigrationActivationReceipt.cache_get_external_calls ?? false)}</p>
        <p>tushare / deepseek / github: {String(storagePhysicalMigrationActivationReceipt.tushare_called ?? false)} / {String(storagePhysicalMigrationActivationReceipt.deepseek_called ?? false)} / {String(storagePhysicalMigrationActivationReceipt.github_called ?? false)}</p>
        <p>missing_evidence: {JSON.stringify(storagePhysicalMigrationActivationReceipt.missing_evidence ?? ["physical schema validation acceptance for all canonical datasets", "manifest validation backed by schema acceptance", "production promotion review"])}</p>
        <p>not_allowed_next_steps: {JSON.stringify(storagePhysicalMigrationActivationReceipt.not_allowed_next_steps ?? ["GET /api/storage physical migration", "GET /api/storage Parquet write", "activation receipt as production storage completion"])}</p>
        <DataLineageTable rows={storagePhysicalMigrationActivationRows} />
      </PacketCard>

      <PacketCard title="DuckDB query result contracts" subtitle="每个本地查询返回投影列、分页和安全边界；不触发刷新" status="query_contract">
        <DataLineageTable rows={queryResultContractRows} />
      </PacketCard>

      <PacketCard title="DuckDB cursor pagination" subtitle="cursor 使用 offset 合同；React 只展示 page_info，不直接读取 Parquet" status="pagination_contract">
        <DataLineageTable rows={queryPageRows} />
      </PacketCard>

      <PacketCard title="DuckDB cursor controls" subtitle="按钮只改变 GET storage cursor；不刷新数据、不写 Parquet、不外联" status="ui_cursor_controls">
        <p>control_policy: read_only_get_cursor_v1</p>
        <p>cursor source: page_info.next_cursor / query_result_contract.next_cursor</p>
        <p>reset cursor 会回到第一页；不会调用 Tushare、DeepSeek、GitHub，也不会执行真实交易。</p>
        <DataLineageTable rows={cursorControlRows} />
        <div className="actions">
          {datasetCards.map((item) => {
            const pageInfo = item.packet.page_info as Record<string, unknown> | undefined;
            const contract = item.packet.query_result_contract as Record<string, unknown> | undefined;
            const nextCursor = storageCursor(pageInfo?.next_cursor ?? contract?.next_cursor);
            return (
              <button key={`${item.key}-next-cursor`} disabled={!nextCursor} onClick={() => loadStorageDatasetPage(item.cursorKey, item.endpoint, nextCursor)}>
                下一页 {item.label}
              </button>
            );
          })}
          {datasetCards.map((item) => (
            <button key={`${item.key}-reset-cursor`} onClick={() => loadStorageDatasetPage(item.cursorKey, item.endpoint, "")}>
              重置 {item.label}
            </button>
          ))}
        </div>
      </PacketCard>

      <PacketCard title="DuckDB dataset filters" subtitle="筛选只作为 GET storage query params；应用筛选会回到第一页" status="ui_dataset_filters">
        <p>filter_policy: read_only_get_query_params_v1</p>
        <p>supported filters: limit / ts_code / trade_date / start_date / end_date / cursor</p>
        <p>不会调用 Tushare、DeepSeek、GitHub，不写 Parquet，不执行真实交易，不修改 strategy action。</p>
        <DataLineageTable rows={datasetFilterRows} />
        <div className="storage-filter-grid">
          {datasetCards.map((item) => {
            const filters = storageFilterDraft(datasetFilters[item.cursorKey]);
            return (
              <div className="storage-filter-panel" key={`${item.key}-filters`}>
                <h4>{item.label}</h4>
                <label>
                  limit
                  <input type="number" min="1" max="10000" value={filters.limit} onChange={(event) => updateStorageDatasetFilter(item.cursorKey, "limit", event.target.value)} />
                </label>
                <label>
                  ts_code
                  <input value={filters.ts_code} onChange={(event) => updateStorageDatasetFilter(item.cursorKey, "ts_code", event.target.value)} />
                </label>
                <label>
                  trade_date
                  <input value={filters.trade_date} onChange={(event) => updateStorageDatasetFilter(item.cursorKey, "trade_date", event.target.value)} />
                </label>
                <label>
                  start_date
                  <input value={filters.start_date} onChange={(event) => updateStorageDatasetFilter(item.cursorKey, "start_date", event.target.value)} />
                </label>
                <label>
                  end_date
                  <input value={filters.end_date} onChange={(event) => updateStorageDatasetFilter(item.cursorKey, "end_date", event.target.value)} />
                </label>
                <div className="actions">
                  <button onClick={() => loadStorageDatasetPage(item.cursorKey, item.endpoint, "")}>应用筛选</button>
                  <button onClick={() => resetStorageDatasetFilters(item.cursorKey, item.endpoint)}>清空筛选</button>
                </div>
              </div>
            );
          })}
        </div>
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

      <PacketCard title="Dataset version manifest evidence" subtitle="只读检查本地 _dataset_versions.json；缺失或不匹配保持 pending，不写 manifest、不读 Parquet payload" status={String(datasetVersionManifestEvidence.status ?? "manifest_missing_validation_pending")}>
        <p>schema_version: {String(datasetVersionManifestEvidence.schema_version ?? "command_center_3_storage_dataset_version_manifest_evidence.v1")}</p>
        <p>scope: {String(datasetVersionManifestEvidence.scope ?? "read_only_local_manifest_evidence_not_manifest_writer")}</p>
        <p>manifest_path: {String(datasetVersionManifestEvidence.manifest_path ?? "--")}</p>
        <p>manifest_exists / validated: {String(datasetVersionManifestEvidence.manifest_exists ?? false)} / {String(datasetVersionManifestEvidence.dataset_version_manifest_validated ?? false)}</p>
        <p>validated / missing / mismatch: {String(datasetVersionManifestEvidence.validated_dataset_count ?? 0)} / {String(datasetVersionManifestEvidence.missing_dataset_count ?? 0)} / {String(datasetVersionManifestEvidence.schema_version_mismatch_count ?? 0)}</p>
        <p>manifest_written_on_get / cache_get_writes_files / reads_parquet_payloads: {String(datasetVersionManifestEvidence.manifest_written_on_get ?? false)} / {String(datasetVersionManifestEvidence.cache_get_writes_files ?? false)} / {String(datasetVersionManifestEvidence.cache_get_reads_parquet_payloads ?? false)}</p>
        <p>dataset_version_manifest_dry_run_route: {String(productionReadiness.dataset_version_manifest_dry_run_route ?? "POST /api/storage/dataset-version-manifest/dry-run")}</p>
        <p>dry_run writes_manifest / writes_parquet: {String(productionReadiness.dataset_version_manifest_dry_run_writes_manifest ?? false)} / {String(productionReadiness.dataset_version_manifest_dry_run_writes_parquet ?? false)}</p>
        <p>dataset_version_manifest_review_route: {String(productionReadiness.dataset_version_manifest_review_route ?? "POST /api/storage/dataset-version-manifest/review")}</p>
        <p>review writes_manifest / production_complete: {String(productionReadiness.dataset_version_manifest_review_writes_manifest ?? false)} / {String(productionReadiness.dataset_version_manifest_review_production_storage_complete ?? false)}</p>
        <p>dataset_version_manifest_write_route: {String(productionReadiness.dataset_version_manifest_write_route ?? "POST /api/storage/dataset-version-manifest/write")}</p>
        <p>write requires_confirm / writes_parquet: {String(productionReadiness.dataset_version_manifest_write_requires_confirm ?? true)} / {String(productionReadiness.dataset_version_manifest_write_writes_parquet ?? false)}</p>
        <p>dataset_version_manifest_validate_route: {String(productionReadiness.dataset_version_manifest_validate_route ?? "POST /api/storage/dataset-version-manifest/validate")}</p>
        <p>validate writes_manifest / production_complete: {String(productionReadiness.dataset_version_manifest_validate_writes_manifest ?? false)} / {String(productionReadiness.dataset_version_manifest_validate_production_storage_complete ?? false)}</p>
        <p>status_counts: {JSON.stringify(datasetVersionManifestEvidenceStatusCounts)}</p>
        <div className="actions">
          <button onClick={launchManifestDryRun}>生成 dataset version manifest dry-run</button>
          <button onClick={launchManifestReview}>审查 dataset version manifest</button>
          <button onClick={launchManifestWrite}>写入 dataset version manifest</button>
          <button onClick={launchManifestValidate}>验证 dataset version manifest</button>
        </div>
        <TaskLaunchReceipt receipt={manifestDryRunReceipt} />
        <TaskStatusPanel taskId={manifestDryRunTaskId} onSuccess={refreshStorage} />
        <TaskLaunchReceipt receipt={manifestReviewReceipt} />
        <TaskStatusPanel taskId={manifestReviewTaskId} onSuccess={refreshStorage} />
        <TaskLaunchReceipt receipt={manifestWriteReceipt} />
        <TaskStatusPanel taskId={manifestWriteTaskId} onSuccess={refreshStorage} />
        <TaskLaunchReceipt receipt={manifestValidateReceipt} />
        <TaskStatusPanel taskId={manifestValidateTaskId} onSuccess={refreshStorage} />
        <DataLineageTable rows={datasetVersionManifestEvidenceRows} />
      </PacketCard>

      <PacketCard title="Cache TTL dry-run" subtitle="按钮门控生成缓存刷新建议；不自动刷新、不调用 Tushare、不写 Parquet" status={String(productionReadiness.cache_ttl_policy ? "button_gated_ready" : "audit_ready")}>
        <p>cache_ttl_policy: {String(productionReadiness.cache_ttl_policy ?? "dry_run_button_gated_no_auto_refresh")}</p>
        <p>cache_ttl_dry_run_route: {String(productionReadiness.cache_ttl_dry_run_route ?? "POST /api/storage/cache-ttl/dry-run")}</p>
        <p>ttl_state_counts: {JSON.stringify(overview.dataset_ttl_state_counts ?? {})}</p>
        <p>refresh_executed / writes_parquet: {String(productionReadiness.cache_ttl_refresh_executed_count ?? 0)} / {String(productionReadiness.cache_ttl_dry_run_writes_parquet ?? false)}</p>
        <div className="actions">
          <button onClick={launchCacheTtlDryRun}>生成 cache TTL dry-run</button>
        </div>
        <TaskLaunchReceipt receipt={cacheTtlDryRunReceipt} />
        <TaskStatusPanel taskId={cacheTtlDryRunTaskId} onSuccess={refreshStorage} />
      </PacketCard>

      <PacketCard title="Compaction dry-run" subtitle="按钮门控生成 Parquet 压缩预检清单；不重写 Parquet、不读行 payload" status={String(productionReadiness.compaction_policy ? "button_gated_ready" : "audit_ready")}>
        <p>compaction_policy: {String(productionReadiness.compaction_policy ?? "dry_run_button_gated_no_parquet_rewrite")}</p>
        <p>compaction_dry_run_route: {String(productionReadiness.compaction_dry_run_route ?? "POST /api/storage/compaction/dry-run")}</p>
        <p>recommended / executed: {String(overview.manual_compaction_recommended_count ?? 0)} / {String(productionReadiness.compaction_executed_count ?? 0)}</p>
        <p>writes_parquet / reads_row_payloads: {String(productionReadiness.compaction_dry_run_writes_parquet ?? false)} / {String(productionReadiness.compaction_dry_run_reads_row_payloads ?? false)}</p>
        <div className="actions">
          <button onClick={launchCompactionDryRun}>生成 compaction dry-run</button>
        </div>
        <TaskLaunchReceipt receipt={compactionDryRunReceipt} />
        <TaskStatusPanel taskId={compactionDryRunTaskId} onSuccess={refreshStorage} />
      </PacketCard>

      <PacketCard title="Schema migration preflight" subtitle="schema/version 迁移预检；只读、不写 Parquet、不读 payload、不外联" status={String(schemaMigration.status ?? "preflight_ready")}>
        <p>mode: {String(schemaMigration.mode ?? "metadata_only_read_only_preflight")}</p>
        <p>contract ready / datasets: {String(schemaMigration.contract_ready_count ?? 0)} / {String(schemaMigration.dataset_count ?? 0)}</p>
        <p>physical validation done / migrations executed: {String(schemaMigration.physical_validation_done_count ?? 0)} / {String(schemaMigration.migration_executed_count ?? 0)}</p>
        <p>cache_get_writes_files / physical_validation_reads_payloads: {String(schemaMigration.cache_get_writes_files ?? false)} / {String(schemaMigration.physical_validation_reads_payloads ?? false)}</p>
        <p>manual_migration_task_required: {String(schemaMigration.manual_migration_task_required ?? true)}</p>
        <p>schema_validation_acceptance_route: {String(productionReadiness.schema_validation_acceptance_route ?? "POST /api/storage/schema-validation/acceptance")}</p>
        <p>acceptance writes_parquet / reads_row_payloads: {String(productionReadiness.schema_validation_acceptance_writes_parquet ?? false)} / {String(productionReadiness.schema_validation_acceptance_reads_row_payloads ?? false)}</p>
        <p>status_counts: {JSON.stringify(schemaMigrationStatusCounts)}</p>
        <div className="actions">
          <button onClick={launchSchemaValidationDryRun}>运行 schema validation dry-run</button>
          <button onClick={launchSchemaValidationAcceptance}>验收 schema metadata</button>
          <button onClick={launchPartitionMigrationDryRun}>生成 partition migration dry-run</button>
        </div>
        <TaskLaunchReceipt receipt={schemaValidationReceipt} />
        <TaskStatusPanel taskId={schemaValidationTaskId} onSuccess={refreshStorage} />
        <TaskLaunchReceipt receipt={schemaAcceptanceReceipt} />
        <TaskStatusPanel taskId={schemaAcceptanceTaskId} onSuccess={refreshStorage} />
        <TaskLaunchReceipt receipt={partitionDryRunReceipt} />
        <TaskStatusPanel taskId={partitionDryRunTaskId} onSuccess={refreshStorage} />
        <DataLineageTable rows={schemaMigrationRows} />
      </PacketCard>

      <PacketCard title="Local artifact hygiene" subtitle="路径级预检；只展示本地生成物边界，不删除、不读 payload、不外联" status={String(artifactHygiene.status ?? "audit_ready")}>
        <p>cleanup_policy: {String(artifactHygiene.cleanup_policy ?? "manual_only_no_delete_on_get")}</p>
        <p>cleanup_task_status: {String(artifactHygiene.cleanup_task_status ?? "dry_run_button_gated")}</p>
        <p>cleanup_dry_run_route: {String(artifactHygiene.cleanup_dry_run_route ?? "POST /api/storage/artifact-hygiene/dry-run")}</p>
        <p>artifact_cleanup_review_status: {String(artifactHygiene.artifact_cleanup_review_status ?? artifactCleanupReview.status ?? "manual_review_ready_no_candidates")}</p>
        <p>delete_files_on_get / auto_cleanup_on_get: {String(artifactHygiene.delete_files_on_get ?? false)} / {String(artifactHygiene.auto_cleanup_on_get ?? false)}</p>
        <p>does_not_read_file_payloads / does_not_scan_secret_values: {String(artifactHygiene.does_not_read_file_payloads ?? true)} / {String(artifactHygiene.does_not_scan_secret_values ?? true)}</p>
        <div className="actions">
          <button onClick={launchArtifactCleanupDryRun}>生成 cleanup dry-run</button>
        </div>
        <TaskLaunchReceipt receipt={dryRunReceipt} />
        <TaskStatusPanel taskId={dryRunTaskId} onSuccess={refreshStorage} />
        <DataLineageTable rows={artifactRows} />
      </PacketCard>

      <PacketCard title="Artifact cleanup manual review" subtitle="dry-run 之后的人工作业合同；不删除、不生成删除命令、不读 payload" status={String(artifactCleanupReview.status ?? "manual_review_ready_no_candidates")}>
        <p>schema_version: {String(artifactCleanupReview.schema_version ?? "command_center_3_storage_artifact_cleanup_review_contract.v1")}</p>
        <p>review_policy: {String(artifactCleanupReview.review_policy ?? "manual_review_required_after_dry_run_before_any_delete")}</p>
        <p>candidate_count / required_review_step_count: {String(artifactCleanupReview.candidate_count ?? 0)} / {String(artifactCleanupReview.required_review_step_count ?? 0)}</p>
        <p>manual_approval_required / delete_executed: {String(artifactCleanupReview.manual_approval_required ?? true)} / {String(artifactCleanupReview.delete_executed ?? false)}</p>
        <p>safe_delete_command_generated / cleanup_review_is_not_delete_execution: {String(artifactCleanupReview.safe_delete_command_generated ?? false)} / {String(artifactCleanupReview.cleanup_review_is_not_delete_execution ?? true)}</p>
        <p>reads_payloads / post_dry_run_external_calls: {String(artifactCleanupReview.reads_payloads ?? false)} / {String(artifactCleanupReview.post_dry_run_external_calls ?? false)}</p>
        <p>production_cleanup_complete: {String(artifactCleanupReview.production_cleanup_complete ?? false)}</p>
        <DataLineageTable rows={artifactCleanupReviewRows} />
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
        <JsonDetails title="artifact cleanup review raw" data={artifactCleanupReview} />
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
