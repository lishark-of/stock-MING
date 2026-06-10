import { useEffect, useState } from "react";
import { getPacket, getPackets } from "../api/client";
import DataLineageTable from "../components/DataLineageTable";
import JsonDetails from "../components/JsonDetails";
import MetricGrid from "../components/MetricGrid";
import PacketCard from "../components/PacketCard";
import StatusBadge from "../components/StatusBadge";

export default function PacketRegistry() {
  const [index, setIndex] = useState<Record<string, unknown>>({});
  const [indexEnvelopeLedger, setIndexEnvelopeLedger] = useState<Array<Record<string, unknown>>>([]);
  const [indexEnvelopeWarnings, setIndexEnvelopeWarnings] = useState<Array<unknown>>([]);
  const [selectedKey, setSelectedKey] = useState("");
  const [packet, setPacket] = useState<Record<string, unknown>>({});
  const [packetEnvelopeLedger, setPacketEnvelopeLedger] = useState<Array<Record<string, unknown>>>([]);
  const [packetEnvelopeWarnings, setPacketEnvelopeWarnings] = useState<Array<unknown>>([]);

  useEffect(() => {
    void getPackets().then((res) => {
      const nextIndex = res.data;
      const keys = nextIndex.available_cache_keys as string[] | undefined;
      setIndexEnvelopeLedger(res.call_ledger ?? []);
      setIndexEnvelopeWarnings(res.warnings ?? []);
      setIndex(nextIndex);
      if (keys?.length) {
        setSelectedKey(keys[0]);
      }
    });
  }, []);

  useEffect(() => {
    if (!selectedKey) return;
    void getPacket(selectedKey).then((res) => {
      setPacketEnvelopeLedger(res.call_ledger ?? []);
      setPacketEnvelopeWarnings(res.warnings ?? []);
      setPacket(res.data);
    });
  }, [selectedKey]);

  const keys = (index.available_cache_keys as string[] | undefined) ?? [];
  const policy = index.cache_api_policy as Record<string, unknown> | undefined;
  const sqliteMeta = index.sqlite_meta as Record<string, unknown> | undefined;
  const storageCatalog = index.storage_catalog as Record<string, unknown> | undefined;
  const storageCatalogRows = (storageCatalog?.dataset_catalog as Array<Record<string, unknown>> | undefined) ?? [];
  const packetMetadata = (sqliteMeta?.packet_metadata as Array<Record<string, unknown>> | undefined) ?? [];
  const taskMetadata = (sqliteMeta?.task_metadata as Array<Record<string, unknown>> | undefined) ?? [];
  const sqliteMetadataSourceRows = (sqliteMeta?.metadata_source_rows as Array<Record<string, unknown>> | undefined) ?? [];
  const persistedKeys = (index.persisted_packet_keys as string[] | undefined) ?? [];
  const snapshotKeys = (index.snapshot_available_keys as string[] | undefined) ?? [];
  const aliasKeys = (index.snapshot_alias_keys as string[] | undefined) ?? [];
  const packetSourceRows = (index.packet_source_rows as Array<Record<string, unknown>> | undefined) ?? [];
  const indexPayloadCallLedger = (index.call_ledger as Array<Record<string, unknown>> | undefined) ?? [];
  const indexCallLedger = indexEnvelopeLedger.length ? indexEnvelopeLedger : indexPayloadCallLedger;
  const indexWarnings = indexEnvelopeWarnings.length ? indexEnvelopeWarnings : ((index.warnings as Array<unknown> | undefined) ?? []);
  const selectedPayloadCallLedger = (packet.call_ledger as Array<Record<string, unknown>> | undefined) ?? [];
  const selectedCallLedger = packetEnvelopeLedger.length ? packetEnvelopeLedger : selectedPayloadCallLedger;
  const selectedWarnings = packetEnvelopeWarnings.length ? packetEnvelopeWarnings : ((packet.warnings as Array<unknown> | undefined) ?? []);
  const selectedBoundaryRows = [
    { boundary: "cache_source", value: String(packet.cache_source ?? "--"), expected: "sqlite_meta | stock_ming_snapshot | local_builder | cache_missing" },
    { boundary: "source_cache_key", value: String(packet.source_cache_key ?? "--"), expected: "safe local key" },
    { boundary: "read_priority", value: "sqlite_meta > snapshot > local_builder > missing", expected: "fixed" },
    { boundary: "external_calls_triggered", value: String(packet.external_calls_triggered ?? packet.cache_api_external_calls_triggered ?? false), expected: "false" },
    { boundary: "tushare_called", value: String(packet.tushare_called ?? packet.cache_api_tushare_called ?? false), expected: "false" },
    { boundary: "deepseek_called", value: String(packet.deepseek_called ?? packet.cache_api_deepseek_called ?? false), expected: "false" },
    { boundary: "github_called", value: String(packet.github_called ?? packet.cache_api_github_called ?? false), expected: "false" },
    { boundary: "does_not_execute_trades", value: String(packet.does_not_execute_trades ?? true), expected: "true" },
    { boundary: "does_not_modify_strategy_action", value: String(packet.does_not_modify_strategy_action ?? true), expected: "true" },
    { boundary: "top_level_call_ledger_count", value: String(packetEnvelopeLedger.length), expected: ">= 0" },
    { boundary: "payload_call_ledger_count", value: String(selectedPayloadCallLedger.length), expected: ">= 0" },
    { boundary: "warning_count", value: String(selectedWarnings.length), expected: ">= 0" }
  ];
  const packetRows = packetSourceRows.length
    ? packetSourceRows
    : keys.map((packetKey) => ({
        packet_key: packetKey,
        read_priority: "sqlite_meta > snapshot > local_builder > missing",
        sqlite_meta: persistedKeys.includes(packetKey),
        snapshot: snapshotKeys.includes(packetKey),
        snapshot_alias: aliasKeys.includes(packetKey)
      }));

  return (
    <>
      <div className="page-head">
        <h1>Packet Registry</h1>
        <StatusBadge label="cache_only" tone="good" />
      </div>

      <MetricGrid
        items={[
          { label: "cache keys", value: keys.length },
          { label: "registry specs", value: index.registry_count as number | undefined },
          { label: "snapshot", value: index.snapshot_available, tone: index.snapshot_available ? "good" : "warn" },
          { label: "persisted packets", value: persistedKeys.length },
          { label: "SQLite packet meta", value: packetMetadata.length },
          { label: "SQLite task meta", value: taskMetadata.length },
          { label: "storage datasets", value: storageCatalog?.dataset_count as number | undefined },
          { label: "index envelope ledger", value: indexCallLedger.length },
          { label: "index warnings", value: indexWarnings.length },
          { label: "selected envelope ledger", value: selectedCallLedger.length },
          { label: "GET cache 外联", value: policy?.get_cache_external_calls === true ? "存在" : "无", tone: policy?.get_cache_external_calls === true ? "bad" : "good" },
          { label: "POST button gated", value: policy?.post_tasks_button_gated, tone: policy?.post_tasks_button_gated === false ? "bad" : "good" },
          { label: "修改 action", value: policy?.does_not_modify_strategy_action === false ? "可能" : "不会", tone: policy?.does_not_modify_strategy_action === false ? "bad" : "good" }
        ]}
      />

      <div className="grid">
        <PacketCard title="Cache API 边界" subtitle="GET /api/packets 与 GET /api/packets/{packet_key} 永不外联" status="read_only">
          <p>本页只读取 FastAPI packet cache，不调用 Tushare、DeepSeek 或 GitHub。</p>
          <p>cache API 永不外联；POST task 才可能触发外部请求，并必须由按钮门控。</p>
          <p>does_not_modify_strategy_action 必须保持为 true，前端不得改写 strategy action。</p>
        </PacketCard>

        <PacketCard title="Packet 详情" subtitle="选择本地 cache key 查看 JSON" status={String(packet.status ?? packet.cache_source ?? "cache")}>
          <label>
            packet key
            <select value={selectedKey} onChange={(event) => setSelectedKey(event.target.value)}>
              {keys.map((packetKey) => (
                <option value={packetKey} key={packetKey}>
                  {packetKey}
                </option>
              ))}
            </select>
          </label>
          <p>selected: {selectedKey || "--"}</p>
          <p>cache source: {String(packet.cache_source ?? "--")}</p>
          <p>external calls: {String(packet.external_calls_triggered ?? packet.cache_api_external_calls_triggered ?? false)}</p>
        </PacketCard>
      </div>

      <PacketCard title="Packet keys" subtitle="本地快照、SQLite metadata 与本地 builder 汇总；读取优先级固定" status="index">
        <DataLineageTable rows={packetRows} />
      </PacketCard>

      <PacketCard title="Packet index envelope call_ledger" subtitle="GET /api/packets 顶层响应血缘；前端优先读取 res.call_ledger" status="lineage">
        <DataLineageTable rows={indexCallLedger} />
      </PacketCard>

      <PacketCard title="Storage catalog summary" subtitle="来自 GET /api/storage/catalog 的只读数据集目录摘要；Packet Registry 不读取 Parquet 数据" status={String(storageCatalog?.status ?? "cache")}>
        <p>dataset count: {String(storageCatalog?.dataset_count ?? 0)}</p>
        <p>cache endpoint: {String(storageCatalog?.cache_endpoint ?? "GET /api/storage/catalog")}</p>
        <p>external calls: {String(storageCatalog?.external_calls_triggered ?? false)}</p>
        <DataLineageTable rows={storageCatalogRows} />
      </PacketCard>

      <PacketCard title="选中 Packet 边界" subtitle="结构化展示外联、交易和 action 边界；不依赖 raw JSON" status="guardrail">
        <DataLineageTable rows={selectedBoundaryRows} />
      </PacketCard>

      <PacketCard title="选中 Packet envelope call_ledger" subtitle="GET /api/packets/{packet_key} 顶层响应血缘；不得包含 token/key 或错误堆栈" status="lineage">
        <DataLineageTable rows={selectedCallLedger} />
      </PacketCard>

      <PacketCard title="SQLite metadata" subtitle="packet/task 元数据只读展示" status={String(sqliteMeta?.sqlite_meta_available ?? false)}>
        <p>does_not_return_payload_json: {String(sqliteMeta?.does_not_return_payload_json ?? true)}</p>
        <p>metadata_safe_columns: {JSON.stringify(sqliteMeta?.metadata_safe_columns ?? {})}</p>
        <p>packet_status_counts: {JSON.stringify(sqliteMeta?.packet_status_counts ?? {})}</p>
        <p>task_status_counts: {JSON.stringify(sqliteMeta?.task_status_counts ?? {})}</p>
        <DataLineageTable rows={sqliteMetadataSourceRows} />
        <DataLineageTable rows={packetMetadata} />
        <JsonDetails title="task metadata" data={taskMetadata} />
      </PacketCard>

      <PacketCard title="原始 packet payload" subtitle="调试用 JSON；不含 token/key" status="safe">
        <JsonDetails title="packet index raw" data={index} />
        <JsonDetails title="selected packet raw" data={packet} open />
      </PacketCard>
    </>
  );
}
