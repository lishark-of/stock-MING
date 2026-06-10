import { useEffect, useState } from "react";
import { getFactorValuesStorage, getSQLiteMetaStorage, getStorageCatalog, getStorageDataset, getStorageOverview } from "../api/client";
import DataLineageTable from "../components/DataLineageTable";
import JsonDetails from "../components/JsonDetails";
import MetricGrid from "../components/MetricGrid";
import PacketCard from "../components/PacketCard";
import StatusBadge from "../components/StatusBadge";

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

  useEffect(() => {
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
    void Promise.all(["daily", "daily-basic", "moneyflow", "backtest-results"].map((dataset) => getStorageDataset(dataset).then((res) => [dataset, res.data] as const))).then((items) =>
      setDatasetDetails(Object.fromEntries(items))
    );
  }, []);

  const datasetStatus = overview.dataset_status as Record<string, unknown> | undefined;
  const datasets = overview.datasets as Array<Record<string, unknown>> | undefined;
  const datasetCatalog =
    (storageCatalog.dataset_catalog as Array<Record<string, unknown>> | undefined) ??
    (overview.dataset_catalog as Array<Record<string, unknown>> | undefined);
  const datasetCards = [
    { key: "factor_values", label: "factor_values", packet: factorValues },
    { key: "daily", label: "daily", packet: datasetDetails.daily ?? {} },
    { key: "daily_basic", label: "daily_basic", packet: datasetDetails["daily-basic"] ?? {} },
    { key: "moneyflow", label: "moneyflow", packet: datasetDetails.moneyflow ?? {} },
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
          { label: "backtest_results", value: String(datasetStatus?.backtest_results ?? "missing") },
          { label: "sqlite meta", value: String(overview.metadata_status ?? sqliteMeta.status ?? "missing") },
          { label: "packets", value: overview.packet_metadata_count ?? sqliteMeta.packet_count ?? 0 },
          { label: "tasks", value: overview.task_metadata_count ?? sqliteMeta.task_count ?? 0 }
        ]}
      />

      <div className="grid">
        <PacketCard title="Parquet / DuckDB Storage" subtitle="只读查看本地数据集状态；不会触发刷新任务" status="cache_only">
          <p>本页只调用 FastAPI storage cache API，不调用 Tushare、DeepSeek 或 GitHub。</p>
          <p>daily / daily_basic / moneyflow / factor_values / backtest_results 通过 DuckDB 查询本地 Parquet；无缓存时只显示 missing。</p>
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

      <PacketCard title="数据集 call_ledger 汇总" subtitle="GET /api/storage/factor-values、daily、daily-basic、moneyflow、backtest-results、sqlite-meta 的本地读取血缘" status="lineage">
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

      <PacketCard title="daily / daily_basic / moneyflow / backtest_results 样例" subtitle="只读本地 Parquet 样例；无缓存时为空表" status="preview">
        <DataLineageTable rows={previewRows} />
      </PacketCard>

      <PacketCard title="原始 storage payload" subtitle="调试用 JSON；cache API 永不外联" status="safe">
        <JsonDetails title="storage overview raw" data={overview} />
        <JsonDetails title="storage catalog raw" data={storageCatalog} />
        <JsonDetails title="factor values raw" data={factorValues} />
        <JsonDetails title="sqlite meta raw" data={sqliteMeta} />
        <JsonDetails title="daily raw" data={datasetDetails.daily ?? {}} />
        <JsonDetails title="daily_basic raw" data={datasetDetails["daily-basic"] ?? {}} />
        <JsonDetails title="moneyflow raw" data={datasetDetails.moneyflow ?? {}} />
        <JsonDetails title="backtest_results raw" data={datasetDetails["backtest-results"] ?? {}} />
      </PacketCard>
    </>
  );
}
