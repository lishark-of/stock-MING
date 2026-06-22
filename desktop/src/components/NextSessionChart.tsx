import type { EChartsOption, MarkAreaComponentOption, SeriesOption } from "echarts";
import { useEffect, useMemo, useState } from "react";
import ChartSafetyStrip from "./ChartSafetyStrip";
import EChartPanel, { type ChartClickParams } from "./EChartPanel";

type ChartPoint = {
  x?: string;
  price?: number;
  source?: string;
  trigger_condition?: string;
  risk_note?: string;
  confidence?: string;
};

type ScenarioSeries = {
  scenario_key?: string;
  scenario_name?: string;
  color?: string;
  source?: string;
  trigger_condition?: string;
  risk_note?: string;
  points?: ChartPoint[];
};

type ReferenceLine = {
  key?: string;
  label?: string;
  value?: number;
  tone?: string;
  source?: string;
};

type OperationZone = {
  zone_key?: string;
  zone_name?: string;
  price_range?: number[];
  tone?: string;
  action_mode?: string;
  source?: string;
  guardrail?: string;
};

type ChartPayload = {
  status?: string;
  source_packet?: string;
  historical_source_label?: string;
  future_source_label?: string;
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

type PointMeta = {
  seriesName: string;
  x: string;
  source: string;
  triggerCondition: string;
  riskNote: string;
  confidence: string;
};

type SelectedInsight = {
  title: string;
  detail: string;
  source: string;
  guardrail: string;
};

function pointTuple(point: ChartPoint): [string, number] | null {
  if (!point.x || typeof point.price !== "number") return null;
  return [point.x, point.price];
}

function metaKey(seriesName: string | undefined, x: string | undefined): string {
  return `${seriesName ?? ""}::${x ?? ""}`;
}

function escapeHtml(value: unknown): string {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function readPointPrice(value: unknown): number | null {
  if (typeof value === "number") return value;
  if (Array.isArray(value) && typeof value[1] === "number") return value[1];
  return null;
}

function readPointXFromParams(params: ChartClickParams | TooltipPoint): string | undefined {
  const value = params.value;
  if (Array.isArray(value) && typeof value[0] === "string") return value[0];
  if (typeof params.name === "string") return params.name;
  if ("axisValue" in params && typeof params.axisValue === "string") return params.axisValue;
  if ("axisValue" in params && typeof params.axisValue === "number") return String(params.axisValue);
  return undefined;
}

type TooltipPoint = {
  axisValue?: string | number;
  marker?: string;
  name?: string;
  seriesName?: string;
  value?: unknown;
};

function useReducedMotionPreference() {
  const [reducedMotion, setReducedMotion] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") return;
    const query = window.matchMedia("(prefers-reduced-motion: reduce)");
    const syncPreference = () => setReducedMotion(query.matches);
    syncPreference();
    if (typeof query.addEventListener === "function") {
      query.addEventListener("change", syncPreference);
      return () => query.removeEventListener("change", syncPreference);
    }
    query.addListener(syncPreference);
    return () => query.removeListener(syncPreference);
  }, []);

  return reducedMotion;
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
  const [selectedInsight, setSelectedInsight] = useState<SelectedInsight | null>(null);
  const reducedMotion = useReducedMotionPreference();
  const historicalPoints = payload?.historical_points ?? [];
  const historical = historicalPoints.map(pointTuple).filter(Boolean) as Array<[string, number]>;
  const scenarioSeries = payload?.scenario_series ?? [];
  const referenceLines = payload?.reference_lines ?? [];
  const operationZones = payload?.operation_zones ?? [];
  const contract = payload?.chart_contract;
  const pointMeta = useMemo(() => {
    const map = new Map<string, PointMeta>();
    historicalPoints.forEach((point) => {
      if (!point.x) return;
      map.set(metaKey("历史 close", point.x), {
        seriesName: "历史 close",
        x: point.x,
        source: point.source ?? payload?.historical_source_label ?? "GET /api/next-session/cache.chart_payload.historical_points",
        triggerCondition: point.trigger_condition ?? "历史段只作为图谱坐标，不触发交易动作。",
        riskNote: point.risk_note ?? "真实 60 日 close 由后端 cache 合同标记；前端不补数。",
        confidence: point.confidence ?? (payload?.uses_real_daily_close ? "real_daily_close" : "cache_or_legacy")
      });
    });
    scenarioSeries.forEach((series) => {
      const seriesName = series.scenario_name ?? "情景路径";
      (series.points ?? []).forEach((point) => {
        if (!point.x) return;
        map.set(metaKey(seriesName, point.x), {
          seriesName,
          x: point.x,
          source: point.source ?? series.source ?? payload?.future_source_label ?? "GET /api/next-session/cache.chart_payload.scenario_series",
          triggerCondition: point.trigger_condition ?? series.trigger_condition ?? "点击情景路径仅显示触发条件；不生成买卖指令。",
          riskNote: point.risk_note ?? series.risk_note ?? "情景路径为解释层预览，不能覆盖 strategy action。",
          confidence: point.confidence ?? "scenario_preview"
        });
      });
    });
    return map;
  }, [historicalPoints, payload?.future_source_label, payload?.historical_source_label, payload?.uses_real_daily_close, scenarioSeries]);

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
            label: { formatter: zone.zone_name ?? zone.zone_key ?? "操作区", position: "insideTop" }
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
        color: zoneColor(zone),
        actionMode: String(zone.action_mode ?? "condition_only"),
        source: String(zone.source ?? "chart_payload.operation_zones"),
        guardrail: String(zone.guardrail ?? "只读区域，不改写 operation_zones 或 strategy action。")
      };
    })
    .filter((item): item is { key: string; label: string; range: string; color: string; actionMode: string; source: string; guardrail: string } => item !== null);
  const chartMotionState = [
    payload.is_exact_next_session_packet === true ? "exact" : "preview",
    payload.uses_real_daily_close === true ? "real-close" : "cache-close",
    payload.warnings?.length ? "warnings" : "clear"
  ].join(" ");

  const tooltipFormatter = (params: unknown): string => {
    const rows = Array.isArray(params) ? (params as TooltipPoint[]) : ([params] as TooltipPoint[]);
    const title = rows[0] ? readPointXFromParams(rows[0]) : "";
    const body = rows
      .map((item) => {
        const x = readPointXFromParams(item);
        const price = readPointPrice(item.value);
        const meta = pointMeta.get(metaKey(item.seriesName, x));
        return [
          `<div><strong>${escapeHtml(item.marker)}${escapeHtml(item.seriesName ?? "路径")}</strong>`,
          price === null ? "" : `价位 ${price.toFixed(2)}`,
          meta?.source ? `来源 ${escapeHtml(meta.source)}` : "",
          meta?.triggerCondition ? `条件 ${escapeHtml(meta.triggerCondition)}` : "",
          meta?.riskNote ? `纪律 ${escapeHtml(meta.riskNote)}` : "",
          "</div>"
        ]
          .filter(Boolean)
          .join(" · ");
      })
      .join("");
    return `<div class="chart-tooltip"><b>${escapeHtml(title)}</b>${body}</div>`;
  };

  const handleChartClick = (params: ChartClickParams) => {
    const x = readPointXFromParams(params);
    const meta = pointMeta.get(metaKey(params.seriesName, x));
    if (meta) {
      setSelectedInsight({
        title: `${meta.seriesName} · ${meta.x}`,
        detail: meta.triggerCondition,
        source: meta.source,
        guardrail: meta.riskNote
      });
      return;
    }
    setSelectedInsight({
      title: String(params.seriesName ?? params.name ?? "图表区域"),
      detail: "点击图表只展示来源、触发条件或区域说明；不会计算 action。",
      source: payload?.source_packet ?? "GET /api/next-session/cache",
      guardrail: "前端不修改价格、持仓、operation_zones 或 strategy action。"
    });
  };

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
    animation: !reducedMotion,
    animationDuration: reducedMotion ? 0 : 360,
    animationDurationUpdate: reducedMotion ? 0 : 260,
    animationEasing: "cubicOut",
    animationEasingUpdate: "cubicOut",
    tooltip: { trigger: "axis", confine: true, formatter: tooltipFormatter },
    legend: { top: 0, type: "scroll" },
    grid: { left: 52, right: 24, top: 52, bottom: 68 },
    dataZoom: [
      { type: "inside", filterMode: "none" },
      { type: "slider", height: 22, bottom: 22, filterMode: "none" }
    ],
    xAxis: { type: "category", data: xLabels, boundaryGap: false },
    yAxis: {
      type: "value",
      min: payload.y_axis_range?.[0] ?? undefined,
      max: payload.y_axis_range?.[1] ?? undefined,
      scale: true
    },
    series
  };

  return (
    <>
      <div className="chart-refresh-frame" data-chart-state={chartMotionState}>
        <EChartPanel option={option} onChartClick={handleChartClick} />
      </div>
      <ChartSafetyStrip
        contract={contract}
        source={payload.source_packet}
        extraItems={[
          { label: "精确图谱", value: payload.is_exact_next_session_packet === true ? "是" : "否" },
          { label: "真实 close", value: payload.uses_real_daily_close === true ? "是" : "待验证" }
        ]}
      />
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
                    <small>{item.actionMode}</small>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="empty-state">暂无操作区。</p>
            )}
          </div>
        </div>
      ) : null}
      <div className="chart-interaction-notes">
        <strong>图谱交互说明</strong>
        <ul>
          <li>先按图表路径、参考线、操作区、缺少证据复核；hover 显示价位来源、触发条件和纪律说明。</li>
          <li>点击情景路径只展开触发条件，不生成交易建议。</li>
          <li>操作区为后端 cache 投影，前端只读渲染，不改 operation_zones。</li>
        </ul>
      </div>
      {selectedInsight ? (
        <div className="chart-selected-insight">
          <strong>{selectedInsight.title}</strong>
          <p>{selectedInsight.detail}</p>
          <small>来源：{selectedInsight.source}</small>
          <small>边界：{selectedInsight.guardrail}</small>
        </div>
      ) : null}
      {payload.warnings?.length ? <p className="risk-note">{payload.warnings[0]}</p> : null}
    </>
  );
}
