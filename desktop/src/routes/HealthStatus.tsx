import { useEffect, useState } from "react";
import { getHealth, getMigrationStatus } from "../api/client";
import DataLineageTable from "../components/DataLineageTable";
import JsonDetails from "../components/JsonDetails";
import MetricGrid from "../components/MetricGrid";
import PacketCard from "../components/PacketCard";
import StatusBadge from "../components/StatusBadge";

export default function HealthStatus() {
  const [health, setHealth] = useState<Record<string, unknown>>({});
  const [healthEnvelopeLedger, setHealthEnvelopeLedger] = useState<Array<Record<string, unknown>>>([]);
  const [healthEnvelopeWarnings, setHealthEnvelopeWarnings] = useState<Array<string>>([]);
  const [migration, setMigration] = useState<Record<string, unknown>>({});

  useEffect(() => {
    void getHealth().then((res) => {
      setHealth(res.data);
      setHealthEnvelopeLedger(res.call_ledger ?? []);
      setHealthEnvelopeWarnings(res.warnings ?? []);
    });
    void getMigrationStatus().then((res) => setMigration(res.data));
  }, []);

  const modelStrategy = health.deepseek_model_strategy as Record<string, unknown> | undefined;
  const modelStrategyRows = [
    { purpose: "default", model: modelStrategy?.default ?? "--", grade: "解释默认" },
    { purpose: "explain", model: modelStrategy?.explain ?? "--", grade: "解释" },
    { purpose: "projection", model: modelStrategy?.projection ?? "--", grade: "次日图谱解释" },
    { purpose: "factor_explain", model: modelStrategy?.factor_explain ?? "--", grade: "因子解释" },
    { purpose: "fast", model: modelStrategy?.fast ?? "--", grade: "轻量" },
    { purpose: "healthcheck", model: modelStrategy?.healthcheck ?? "--", grade: "健康检查" },
    { purpose: "feeder", model: modelStrategy?.feeder ?? "--", grade: "自动喂数" }
  ];
  const progress = (migration.progress_baseline as Array<Record<string, unknown>> | undefined) ?? [];
  const migrationPolicy = migration.api_policy as Record<string, unknown> | undefined;
  const healthWarnings = healthEnvelopeWarnings.length ? healthEnvelopeWarnings : ((health.warnings as Array<string> | undefined) ?? []);

  return (
    <>
      <div className="page-head">
        <h1>系统健康</h1>
        <StatusBadge label={String(health.status ?? "loading")} tone={health.status === "ok" ? "good" : "warn"} />
      </div>

      <MetricGrid
        items={[
          { label: "FastAPI", value: health.status as string | undefined, tone: health.status === "ok" ? "good" : "warn" },
          { label: "startup external calls", value: health.external_calls_on_startup === true ? "存在" : "无", tone: health.external_calls_on_startup === true ? "bad" : "good" },
          { label: "Tushare", value: health.tushare_called === true ? "已调用" : "未调用", tone: health.tushare_called === true ? "bad" : "good" },
          { label: "DeepSeek", value: health.deepseek_called === true ? "已调用" : "未调用", tone: health.deepseek_called === true ? "bad" : "good" },
          { label: "GitHub", value: health.github_called === true ? "已调用" : "未调用", tone: health.github_called === true ? "bad" : "good" },
          { label: "真实交易", value: health.real_trading_enabled === true ? "启用" : "禁用", tone: health.real_trading_enabled === true ? "bad" : "good" },
          { label: "Streamlit", value: String(health.legacy_streamlit ?? "legacy/admin/debug") },
          { label: "迁移基线", value: String(migration.status ?? "loading") },
          { label: "cache only", value: migrationPolicy?.cache_only, tone: migrationPolicy?.cache_only === false ? "bad" : "good" },
          { label: "health envelope ledger", value: healthEnvelopeLedger.length },
          { label: "health warnings", value: healthWarnings.length }
        ]}
      />

      <div className="grid">
        <PacketCard title="启动安全边界" subtitle="GET /health 只读；不触发 Tushare、DeepSeek 或 GitHub" status="read_only">
          <p>Command Center 3.0 启动健康检查只展示服务状态，不创建任务，不读取 token/key，不执行真实交易。</p>
          <p>所有重计算和外部请求仍必须通过按钮门控 POST task，并由 call_ledger 审计。</p>
        </PacketCard>

        <PacketCard title="DeepSeek 模型策略" subtitle="可配置模型名；不在调用点硬编码；不展示密钥" status="config">
          <DataLineageTable rows={modelStrategyRows} />
          <p>contains_secret: {String(modelStrategy?.contains_secret ?? false)}</p>
          <p>source: {String(modelStrategy?.source ?? "config")}</p>
        </PacketCard>
      </div>

      <PacketCard title="迁移基线" subtitle="用户给定长期参考进度；只读展示，不重新估算" status={String(migration.status ?? "baseline")}>
        <DataLineageTable rows={progress} />
      </PacketCard>

      <PacketCard title="GET health envelope call_ledger" subtitle="GET /health 顶层响应血缘；前端优先读取 res.call_ledger" status="lineage">
        <DataLineageTable rows={healthEnvelopeLedger} />
      </PacketCard>

      <PacketCard title="GET health envelope warnings" subtitle="顶层响应提示；不包含 token/key/错误堆栈" status="warnings">
        <DataLineageTable rows={healthWarnings.map((warning, index) => ({ index: index + 1, warning }))} />
      </PacketCard>

      <PacketCard title="原始健康 payload" subtitle="调试用 JSON；不含 token/key" status="safe">
        <JsonDetails title="health raw" data={health} />
        <JsonDetails title="migration raw" data={migration} />
      </PacketCard>
    </>
  );
}
