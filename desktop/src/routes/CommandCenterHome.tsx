import { useEffect, useState } from "react";
import { getFactorQuantCache, getHealth, getNextSessionCache, getPackets, getSerenityCache } from "../api/client";
import PacketCard from "../components/PacketCard";
import StatusBadge from "../components/StatusBadge";

export default function CommandCenterHome() {
  const [health, setHealth] = useState<Record<string, unknown>>({});
  const [packets, setPackets] = useState<Record<string, unknown>>({});
  const [factor, setFactor] = useState<Record<string, unknown>>({});
  const [next, setNext] = useState<Record<string, unknown>>({});
  const [serenity, setSerenity] = useState<Record<string, unknown>>({});

  useEffect(() => {
    void getHealth().then((res) => setHealth(res.data));
    void getPackets().then((res) => setPackets(res.data));
    void getFactorQuantCache().then((res) => setFactor(res.data));
    void getNextSessionCache().then((res) => setNext(res.data));
    void getSerenityCache().then((res) => setSerenity(res.data));
  }, []);

  return (
    <>
      <div className="page-head">
        <h1>Command Center 3.0</h1>
        <StatusBadge label={health.status === "ok" ? "FastAPI online" : "waiting"} tone={health.status === "ok" ? "good" : "warn"} />
      </div>
      <div className="grid">
        <PacketCard title="FastAPI Health" subtitle="启动时不调用 Tushare / DeepSeek / GitHub" status={String(health.status ?? "unknown")}>
          <pre>{JSON.stringify(health, null, 2)}</pre>
        </PacketCard>
        <PacketCard title="Packet Registry" subtitle="现有 packet contract 只读映射" status="cache">
          <p>cache keys: {String((packets.available_cache_keys as unknown[] | undefined)?.length ?? 0)}</p>
        </PacketCard>
        <PacketCard title="次日操作图谱 cache" subtitle="GET cache，不刷新" status={String(next.status ?? "cache")}>
          <p>{String(next.summary ?? "等待缓存")}</p>
        </PacketCard>
        <PacketCard title="Factor Quant Hub cache" subtitle="多因子量化图谱 cache-only" status={String((factor.runtime as Record<string, unknown> | undefined)?.status ?? "cache")}>
          <p>mode: {String(factor.mode ?? "cache_only")}</p>
        </PacketCard>
        <PacketCard title="Serenity 方法雷达 cache" subtitle="本地方法来源基线" status={String(serenity.github_status ?? "local")}>
          <p>DeepSeek: 不调用</p>
        </PacketCard>
      </div>
    </>
  );
}
