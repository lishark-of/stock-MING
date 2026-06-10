import { useEffect, useState } from "react";
import { getPacket, getPackets } from "../api/client";
import DataLineageTable from "../components/DataLineageTable";
import JsonDetails from "../components/JsonDetails";
import MetricGrid from "../components/MetricGrid";
import PacketCard from "../components/PacketCard";
import StatusBadge from "../components/StatusBadge";

export default function PacketRegistry() {
  const [index, setIndex] = useState<Record<string, unknown>>({});
  const [selectedKey, setSelectedKey] = useState("");
  const [packet, setPacket] = useState<Record<string, unknown>>({});

  useEffect(() => {
    void getPackets().then((res) => {
      const nextIndex = res.data;
      const keys = nextIndex.available_cache_keys as string[] | undefined;
      setIndex(nextIndex);
      if (keys?.length) {
        setSelectedKey(keys[0]);
      }
    });
  }, []);

  useEffect(() => {
    if (!selectedKey) return;
    void getPacket(selectedKey).then((res) => setPacket(res.data));
  }, [selectedKey]);

  const keys = (index.available_cache_keys as string[] | undefined) ?? [];
  const policy = index.cache_api_policy as Record<string, unknown> | undefined;
  const sqliteMeta = index.sqlite_meta as Record<string, unknown> | undefined;
  const packetMetadata = (sqliteMeta?.packet_metadata as Array<Record<string, unknown>> | undefined) ?? [];
  const taskMetadata = (sqliteMeta?.task_metadata as Array<Record<string, unknown>> | undefined) ?? [];
  const persistedKeys = (index.persisted_packet_keys as string[] | undefined) ?? [];
  const snapshotKeys = (index.snapshot_available_keys as string[] | undefined) ?? [];
  const aliasKeys = (index.snapshot_alias_keys as string[] | undefined) ?? [];
  const packetRows = keys.map((packetKey) => ({
    packet_key: packetKey,
    persisted: persistedKeys.includes(packetKey),
    snapshot: snapshotKeys.includes(packetKey),
    alias: aliasKeys.includes(packetKey)
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

      <PacketCard title="Packet keys" subtitle="本地快照、SQLite metadata 与本地 builder 汇总" status="index">
        <DataLineageTable rows={packetRows} />
      </PacketCard>

      <PacketCard title="SQLite metadata" subtitle="packet/task 元数据只读展示" status={String(sqliteMeta?.sqlite_meta_available ?? false)}>
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
