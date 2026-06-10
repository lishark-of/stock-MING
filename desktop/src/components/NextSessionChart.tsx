import type { EChartsOption, SeriesOption } from "echarts";
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
  label?: string;
  value?: number;
};

type OperationZone = {
  zone_key?: string;
  zone_name?: string;
  price_range?: number[];
  tone?: string;
};

type ChartPayload = {
  status?: string;
  historical_points?: ChartPoint[];
  scenario_series?: ScenarioSeries[];
  reference_lines?: ReferenceLine[];
  operation_zones?: OperationZone[];
  y_axis_range?: Array<number | null>;
  warnings?: string[];
};

function pointTuple(point: ChartPoint): [string, number] | null {
  if (!point.x || typeof point.price !== "number") return null;
  return [point.x, point.price];
}

export default function NextSessionChart({ payload }: { payload: ChartPayload | null | undefined }) {
  const historical = (payload?.historical_points ?? []).map(pointTuple).filter(Boolean) as Array<[string, number]>;
  const scenarioSeries = payload?.scenario_series ?? [];
  const referenceLines = payload?.reference_lines ?? [];
  const operationZones = payload?.operation_zones ?? [];

  if (!payload || payload.status === "missing" || (!historical.length && !scenarioSeries.length)) {
    return <p className="empty-state">暂无可绘制的次日操作图谱缓存。</p>;
  }

  const xLabels = Array.from(
    new Set([
      ...historical.map(([x]) => x),
      ...scenarioSeries.flatMap((series) => (series.points ?? []).map((point) => point.x).filter(Boolean) as string[])
    ])
  );

  const markLineData = referenceLines
    .filter((line) => typeof line.value === "number")
    .map((line) => ({
      name: line.label ?? "参考线",
      yAxis: line.value,
      label: { formatter: line.label ?? "参考线" }
    }));
  const markAreaData = operationZones
    .map((zone) => {
      const rawLow = zone.price_range?.[0];
      const rawHigh = zone.price_range?.[1];
      if (typeof rawLow !== "number" || typeof rawHigh !== "number") return null;
      const low = Math.min(rawLow, rawHigh);
      const high = Math.max(rawLow, rawHigh);
      const color = zone.tone === "high" || zone.tone === "red" ? "rgba(239, 68, 68, 0.10)" : "rgba(37, 99, 235, 0.08)";
      return [
        {
          name: zone.zone_name ?? zone.zone_key ?? "操作区",
          yAxis: low,
          itemStyle: { color },
          label: { formatter: zone.zone_name ?? zone.zone_key ?? "操作区" }
        },
        { yAxis: high }
      ];
    })
    .filter((item): item is Array<Record<string, unknown>> => item !== null);

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
      {payload.warnings?.length ? <p className="risk-note">{payload.warnings[0]}</p> : null}
    </>
  );
}
