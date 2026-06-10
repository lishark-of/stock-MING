import type { EChartsOption, MarkAreaComponentOption, SeriesOption } from "echarts";
import EChartPanel from "./EChartPanel";

type ChartPoint = {
  x?: string;
  price?: number;
};

type ScenarioSeries = {
  scenario_name?: string;
  color?: string;
  points?: ChartPoint[];
};

type ReferenceLine = {
  key?: string;
  label?: string;
  value?: number;
  tone?: string;
};

type OperationZone = {
  zone_key?: string;
  zone_name?: string;
  price_range?: number[];
  tone?: string;
};

type ChartPayload = {
  status?: string;
  source_packet?: string;
  is_exact_next_session_packet?: boolean;
  uses_real_daily_close?: boolean;
  historical_points?: ChartPoint[];
  scenario_series?: ScenarioSeries[];
  reference_lines?: ReferenceLine[];
  operation_zones?: OperationZone[];
  y_axis_range?: Array<number | null>;
  chart_contract?: {
    renderer?: string;
    schema_version?: string;
    source_packet?: string;
    external_calls_triggered?: boolean;
    tushare_called?: boolean;
    deepseek_called?: boolean;
    github_called?: boolean;
    does_not_execute_trades?: boolean;
    frontend_computes_trade_action?: boolean;
    does_not_modify_action?: boolean;
    does_not_modify_operation_zones?: boolean;
  };
  warnings?: string[];
};

function pointTuple(point: ChartPoint): [string, number] | null {
  if (!point.x || typeof point.price !== "number") return null;
  return [point.x, point.price];
}

function referenceColor(line: ReferenceLine): string {
  const key = String(line.key ?? "").toLowerCase();
  const tone = String(line.tone ?? "").toLowerCase();
  if (key.includes("current") || tone === "blue") return "#2563eb";
  if (key.includes("cost") || tone === "orange") return "#f97316";
  if (key.includes("support") || tone === "green") return "#16a34a";
  if (key.includes("resistance") || tone === "red") return "#dc2626";
  if (key.includes("limit") && (tone === "red" || tone === "green")) return tone === "red" ? "#dc2626" : "#16a34a";
  return "#64748b";
}

function referenceLineType(line: ReferenceLine): "solid" | "dashed" | "dotted" {
  const key = String(line.key ?? "").toLowerCase();
  if (key.includes("current")) return "solid";
  if (key.includes("cost")) return "dashed";
  if (key.includes("support") || key.includes("resistance")) return "dotted";
  return "dashed";
}

function zoneColor(zone: OperationZone): string {
  const key = String(zone.zone_key ?? "").toLowerCase();
  const tone = String(zone.tone ?? "").toLowerCase();
  if (key.includes("risk") || key.includes("forbid") || tone === "high" || tone === "red") return "rgba(239, 68, 68, 0.12)";
  if (key.includes("support") || key.includes("buy") || tone === "green") return "rgba(22, 163, 74, 0.10)";
  if (key.includes("reduce") || key.includes("take") || tone === "orange") return "rgba(249, 115, 22, 0.12)";
  return "rgba(37, 99, 235, 0.08)";
}

function lineStyleLabel(type: "solid" | "dashed" | "dotted"): string {
  if (type === "solid") return "实线";
  if (type === "dotted") return "点线";
  return "虚线";
}

export default function NextSessionChart({ payload }: { payload: ChartPayload | null | undefined }) {
  const historical = (payload?.historical_points ?? []).map(pointTuple).filter(Boolean) as Array<[string, number]>;
  const scenarioSeries = payload?.scenario_series ?? [];
  const referenceLines = payload?.reference_lines ?? [];
  const operationZones = payload?.operation_zones ?? [];
  const contract = payload?.chart_contract;
  const mayModifyOperationZones = Object.is(contract?.does_not_modify_operation_zones, false);

  if (!payload || payload.status === "missing" || (!historical.length && !scenarioSeries.length)) {
    return (
      <div className="chart-empty-state">
        <strong>暂无可绘制的次日操作图谱缓存。</strong>
        <p>GET cache 只读返回缺口提示，不触发 Tushare、DeepSeek 或 GitHub。</p>
      </div>
    );
  }

  const xLabels = Array.from(
    new Set([
      ...historical.map(([x]) => x),
      ...scenarioSeries.flatMap((series) => (series.points ?? []).map((point) => point.x).filter(Boolean) as string[])
    ])
  );

  const markLineData: Array<Record<string, unknown>> = referenceLines
    .filter((line) => typeof line.value === "number")
    .map((line) => ({
      name: line.label ?? "参考线",
      yAxis: line.value,
      lineStyle: { color: referenceColor(line), type: referenceLineType(line), width: 1.4 },
      label: { formatter: line.label ?? "参考线", color: referenceColor(line) }
    }));
  if (xLabels.includes("T0")) {
    markLineData.push({
      name: "T0 分割线",
      xAxis: "T0",
      lineStyle: { color: "#0f172a", type: "dashed", width: 1.2 },
      label: { formatter: "T0", color: "#0f172a" }
    });
  }
  const markAreaData: NonNullable<MarkAreaComponentOption["data"]> = operationZones
    .flatMap((zone) => {
      const rawLow = zone.price_range?.[0];
      const rawHigh = zone.price_range?.[1];
      if (typeof rawLow !== "number" || typeof rawHigh !== "number") return [];
      const low = Math.min(rawLow, rawHigh);
      const high = Math.max(rawLow, rawHigh);
      const color = zoneColor(zone);
      return [
        [
          {
            name: zone.zone_name ?? zone.zone_key ?? "操作区",
            yAxis: low,
            itemStyle: { color },
            label: { formatter: zone.zone_name ?? zone.zone_key ?? "操作区" }
          },
          { yAxis: high }
        ]
      ];
    });
  const referenceLegend = referenceLines
    .filter((line) => typeof line.value === "number")
    .map((line) => {
      const style = referenceLineType(line);
      return {
        key: String(line.key ?? line.label ?? "reference_line"),
        label: String(line.label ?? line.key ?? "参考线"),
        value: Number(line.value).toFixed(2),
        color: referenceColor(line),
        style,
        styleLabel: lineStyleLabel(style)
      };
    });
  if (xLabels.includes("T0")) {
    referenceLegend.push({
      key: "t0_split",
      label: "T0 分割线",
      value: "时间分割",
      color: "#0f172a",
      style: "dashed",
      styleLabel: "虚线"
    });
  }
  const operationLegend = operationZones
    .map((zone) => {
      const rawLow = zone.price_range?.[0];
      const rawHigh = zone.price_range?.[1];
      if (typeof rawLow !== "number" || typeof rawHigh !== "number") return null;
      const low = Math.min(rawLow, rawHigh);
      const high = Math.max(rawLow, rawHigh);
      return {
        key: String(zone.zone_key ?? zone.zone_name ?? "operation_zone"),
        label: String(zone.zone_name ?? zone.zone_key ?? "操作区"),
        range: `${low.toFixed(2)} - ${high.toFixed(2)}`,
        color: zoneColor(zone)
      };
    })
    .filter((item): item is { key: string; label: string; range: string; color: string } => item !== null);

  const series: SeriesOption[] = [
    {
      name: "历史 close",
      type: "line",
      smooth: true,
      symbolSize: 6,
      data: historical,
      markLine: {
        silent: true,
        data: markLineData
      },
      markArea: markAreaData.length
        ? {
            silent: true,
            data: markAreaData
          }
        : undefined
    },
    ...scenarioSeries.map((item) => ({
      name: item.scenario_name ?? "情景路径",
      type: "line" as const,
      smooth: true,
      lineStyle: { type: "dashed" as const, color: item.color },
      itemStyle: { color: item.color },
      data: (item.points ?? []).map(pointTuple).filter(Boolean) as Array<[string, number]>
    }))
  ];

  const option: EChartsOption = {
    tooltip: { trigger: "axis" },
    legend: { top: 0 },
    grid: { left: 52, right: 24, top: 48, bottom: 36 },
    xAxis: { type: "category", data: xLabels },
    yAxis: {
      type: "value",
      min: payload.y_axis_range?.[0] ?? undefined,
      max: payload.y_axis_range?.[1] ?? undefined
    },
    series
  };

  return (
    <>
      <EChartPanel option={option} />
      <div className="chart-safety-strip">
        <span>来源：{String(contract?.source_packet ?? payload.source_packet ?? "cache_payload")}</span>
        <span>精确图谱：{payload.is_exact_next_session_packet === true ? "是" : "否"}</span>
        <span>真实 close：{payload.uses_real_daily_close === true ? "是" : "待验证"}</span>
        <span>外部调用：{contract?.external_calls_triggered === true ? "存在" : "无"}</span>
        <span>Tushare：{contract?.tushare_called === true ? "已调用" : "未调用"}</span>
        <span>DeepSeek：{contract?.deepseek_called === true ? "已调用" : "未调用"}</span>
        <span>GitHub：{contract?.github_called === true ? "已调用" : "未调用"}</span>
        <span>真实交易：{contract?.does_not_execute_trades === false ? "可能" : "禁止"}</span>
        <span>前端算交易动作：{contract?.frontend_computes_trade_action === true ? "是" : "否"}</span>
        <span>改 action：{contract?.does_not_modify_action === false ? "可能" : "不会"}</span>
        <span>改操作区：{mayModifyOperationZones ? "可能" : "不会"}</span>
      </div>
      {referenceLegend.length || operationLegend.length ? (
        <div className="chart-legend-grid">
          <div className="chart-legend-block">
            <strong>参考线图例</strong>
            {referenceLegend.length ? (
              <ul className="chart-legend-list">
                {referenceLegend.map((item) => (
                  <li key={item.key}>
                    <span className="chart-legend-line" style={{ borderTopColor: item.color, borderTopStyle: item.style }} />
                    <span>{item.label}</span>
                    <em>{item.value}</em>
                    <small>{item.styleLabel}</small>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="empty-state">暂无参考线。</p>
            )}
          </div>
          <div className="chart-legend-block">
            <strong>操作区图例</strong>
            {operationLegend.length ? (
              <ul className="chart-legend-list">
                {operationLegend.map((item) => (
                  <li key={item.key}>
                    <span className="chart-legend-zone" style={{ backgroundColor: item.color }} />
                    <span>{item.label}</span>
                    <em>{item.range}</em>
                    <small>只读区域</small>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="empty-state">暂无操作区。</p>
            )}
          </div>
        </div>
      ) : null}
      {payload.warnings?.length ? <p className="risk-note">{payload.warnings[0]}</p> : null}
    </>
  );
}
