import { useEffect, useState } from "react";
import { getChokepointCache, getFactorQuantCache, getHealth, getNextSessionCache, getPackets, getSerenityCache, getTasks } from "../api/client";
import JsonDetails from "../components/JsonDetails";
import MetricGrid from "../components/MetricGrid";
import PacketCard from "../components/PacketCard";
import StatusBadge from "../components/StatusBadge";

export default function CommandCenterHome() {
  const [health, setHealth] = useState<Record<string, unknown>>({});
  const [packets, setPackets] = useState<Record<string, unknown>>({});
  const [factor, setFactor] = useState<Record<string, unknown>>({});
  const [next, setNext] = useState<Record<string, unknown>>({});
  const [serenity, setSerenity] = useState<Record<string, unknown>>({});
  const [chokepoint, setChokepoint] = useState<Record<string, unknown>>({});
  const [tasks, setTasks] = useState<Array<Record<string, unknown>>>([]);

  useEffect(() => {
    void getHealth().then((res) => setHealth(res.data));
    void getPackets().then((res) => setPackets(res.data));
    void getFactorQuantCache().then((res) => setFactor(res.data));
    void getNextSessionCache().then((res) => setNext(res.data));
    void getSerenityCache().then((res) => setSerenity(res.data));
    void getChokepointCache().then((res) => setChokepoint(res.data));
    void getTasks().then((res) => setTasks(res.data.tasks ?? []));
  }, []);

  const packetKeys = packets.available_cache_keys as unknown[] | undefined;
  const snapshotAvailable = Boolean(packets.snapshot_available);

  return (
    <>
      <div className="page-head">
        <h1>Command Center 3.0</h1>
        <StatusBadge label={health.status === "ok" ? "FastAPI online" : "waiting"} tone={health.status === "ok" ? "good" : "warn"} />
      </div>
      <MetricGrid
        items={[
          { label: "FastAPI", value: String(health.status ?? "unknown"), tone: health.status === "ok" ? "good" : "warn" },
          { label: "本地快照", value: snapshotAvailable, tone: snapshotAvailable ? "good" : "warn" },
          { label: "cache keys", value: packetKeys?.length ?? 0 },
          { label: "任务记录", value: tasks.length },
          { label: "外部启动调用", value: health.external_calls_on_startup === true ? "存在" : "无", tone: health.external_calls_on_startup === true ? "bad" : "good" }
        ]}
      />
      <div className="grid">
        <PacketCard title="Packet Registry" subtitle="现有 packet contract 只读映射" status={snapshotAvailable ? "snapshot" : "cache"}>
          <p>本地快照路径：{String(packets.snapshot_cache_path ?? "--")}</p>
          <p>alias keys: {String((packets.snapshot_alias_keys as unknown[] | undefined)?.length ?? 0)}</p>
          <JsonDetails title="packet index 明细" data={packets} />
        </PacketCard>
        <PacketCard title="次日操作图谱 cache" subtitle="GET cache，不刷新，不改 action" status={String(next.status ?? "cache")}>
          <p>{String(next.summary ?? "等待缓存")}</p>
          <p>legacy projection: {String((next.legacy_projection_cache as Record<string, unknown> | undefined)?.available ?? false)}</p>
        </PacketCard>
        <PacketCard title="Factor Quant Hub cache" subtitle="多因子量化图谱 cache-only" status={String((factor.runtime as Record<string, unknown> | undefined)?.status ?? "cache")}>
          <p>mode: {String(factor.mode ?? "cache_only")}</p>
          <p>coverage: {String((factor.runtime as Record<string, unknown> | undefined)?.coverage ?? "--")}</p>
          <p>core action: {String((factor.governance as Record<string, unknown> | undefined)?.allow_core_action ?? false)}</p>
        </PacketCard>
        <PacketCard title="Serenity 方法雷达 cache" subtitle="本地方法来源基线" status={String(serenity.github_status ?? "local")}>
          <p>DeepSeek: 不调用</p>
          <p>repositories: {String((serenity.repositories as unknown[] | undefined)?.length ?? 0)}</p>
        </PacketCard>
        <PacketCard title="产业链瓶颈扫描 cache" subtitle="GET cache 不触发 DeepSeek" status={String(chokepoint.status ?? "cache")}>
          <p>{String(chokepoint.summary ?? "等待缓存")}</p>
        </PacketCard>
        <PacketCard title="任务状态" subtitle="POST 返回 task_id，页面轮询 FastAPI" status="local">
          <p>最近任务数：{tasks.length}</p>
          <JsonDetails title="任务列表" data={tasks} />
        </PacketCard>
      </div>
    </>
  );
}
