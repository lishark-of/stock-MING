import { useEffect, useState } from "react";
import { getFactorValuesStorage, getStorageOverview } from "../api/client";
import DataLineageTable from "../components/DataLineageTable";
import JsonDetails from "../components/JsonDetails";
import MetricGrid from "../components/MetricGrid";
import PacketCard from "../components/PacketCard";
import StatusBadge from "../components/StatusBadge";

export default function StorageOverview() {
  const [overview, setOverview] = useState<Record<string, unknown>>({});
  const [factorValues, setFactorValues] = useState<Record<string, unknown>>({});

  useEffect(() => {
    void getStorageOverview().then((res) => setOverview(res.data));
    void getFactorValuesStorage().then((res) => setFactorValues(res.data));
  }, []);

  const datasetStatus = overview.dataset_status as Record<string, unknown> | undefined;
  const datasets = overview.datasets as Array<Record<string, unknown>> | undefined;
  const factorMetadata = factorValues.metadata as Record<string, unknown> | undefined;
  const factorQuery = factorValues.query as Record<string, unknown> | undefined;
  const factorRows = (factorQuery?.rows as Array<Record<string, unknown>> | undefined) ?? [];

  return (
    <>
      <div className="page-head">
        <h1>存储层</h1>
        <StatusBadge label={String(overview.store ?? "parquet_duckdb")} tone="neutral" />
      </div>

      <MetricGrid
        items={[
          { label: "store", value: overview.store as string | undefined },
          { label: "cache only", value: overview.cache_only, tone: overview.cache_only === false ? "bad" : "good" },
          { label: "external calls", value: overview.external_calls_triggered === true ? "存在" : "无", tone: overview.external_calls_triggered === true ? "bad" : "good" },
          { label: "Tushare", value: overview.tushare_called === true ? "已调用" : "未调用", tone: overview.tushare_called === true ? "bad" : "good" },
          { label: "DeepSeek", value: overview.deepseek_called === true ? "已调用" : "未调用", tone: overview.deepseek_called === true ? "bad" : "good" },
          { label: "GitHub", value: overview.github_called === true ? "已调用" : "未调用", tone: overview.github_called === true ? "bad" : "good" },
          { label: "真实交易", value: overview.does_not_execute_trades === false ? "可能" : "禁止", tone: overview.does_not_execute_trades === false ? "bad" : "good" },
          { label: "修改 action", value: overview.does_not_modify_strategy_action === false ? "可能" : "不会", tone: overview.does_not_modify_strategy_action === false ? "bad" : "good" },
          { label: "factor_values", value: String(datasetStatus?.factor_values ?? "missing") },
          { label: "daily", value: String(datasetStatus?.daily ?? "missing") },
          { label: "moneyflow", value: String(datasetStatus?.moneyflow ?? "missing") }
        ]}
      />

      <div className="grid">
        <PacketCard title="Parquet / DuckDB Storage" subtitle="只读查看本地数据集状态；不会触发刷新任务" status="cache_only">
          <p>本页只调用 FastAPI storage cache API，不调用 Tushare、DeepSeek 或 GitHub。</p>
          <p>daily / moneyflow / factor_values 通过 DuckDB 查询本地 Parquet；无缓存时只显示 missing。</p>
          <p>does_not_execute_trades 与 does_not_modify_strategy_action 必须保持为 true。</p>
        </PacketCard>

        <PacketCard title="Factor Values" subtitle="runtime.factor_values 本地落盘状态" status={String(factorMetadata?.status ?? "missing")}>
          <p>row_count: {String(factorValues.row_count ?? factorQuery?.row_count ?? 0)}</p>
          <p>path: {String(factorValues.path ?? factorMetadata?.path ?? "--")}</p>
          <p>cache_only: {String(factorValues.cache_only ?? true)}</p>
        </PacketCard>
      </div>

      <PacketCard title="数据集状态" subtitle="本地 Parquet 数据集元数据" status="overview">
        <DataLineageTable rows={datasets ?? []} />
      </PacketCard>

      <PacketCard title="factor_values 样例" subtitle="只展示安全标量；不含 token/key" status="preview">
        <DataLineageTable rows={factorRows} />
      </PacketCard>

      <PacketCard title="原始 storage payload" subtitle="调试用 JSON；cache API 永不外联" status="safe">
        <JsonDetails title="storage overview raw" data={overview} />
        <JsonDetails title="factor values raw" data={factorValues} />
      </PacketCard>
    </>
  );
}
