import type { EChartsOption } from "echarts";
import { BarChart, LineChart } from "echarts/charts";
import {
  DataZoomComponent,
  GridComponent,
  LegendComponent,
  MarkAreaComponent,
  MarkLineComponent,
  TooltipComponent
} from "echarts/components";
import { init, use } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { useEffect, useRef } from "react";

use([
  BarChart,
  LineChart,
  DataZoomComponent,
  GridComponent,
  LegendComponent,
  MarkAreaComponent,
  MarkLineComponent,
  TooltipComponent,
  CanvasRenderer
]);

export type ChartClickParams = {
  componentType?: string;
  seriesName?: string;
  name?: string;
  value?: unknown;
  dataIndex?: number;
  seriesIndex?: number;
};

export default function EChartPanel({
  option,
  onChartClick
}: {
  option: EChartsOption;
  onChartClick?: (params: ChartClickParams) => void;
}) {
  const ref = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!ref.current) return;
    const chart = init(ref.current);
    chart.setOption(option);
    const clickHandler = onChartClick
      ? (params: unknown) => onChartClick(params as ChartClickParams)
      : undefined;
    if (clickHandler) chart.on("click", clickHandler);
    const onResize = () => chart.resize();
    window.addEventListener("resize", onResize);
    return () => {
      window.removeEventListener("resize", onResize);
      if (clickHandler) chart.off("click", clickHandler);
      chart.dispose();
    };
  }, [option, onChartClick]);

  return <div className="chart-panel" ref={ref} />;
}
