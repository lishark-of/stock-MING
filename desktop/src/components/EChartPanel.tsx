import * as echarts from "echarts";
import { useEffect, useRef } from "react";

export default function EChartPanel({ option }: { option: echarts.EChartsOption }) {
  const ref = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!ref.current) return;
    const chart = echarts.init(ref.current);
    chart.setOption(option);
    const onResize = () => chart.resize();
    window.addEventListener("resize", onResize);
    return () => {
      window.removeEventListener("resize", onResize);
      chart.dispose();
    };
  }, [option]);

  return <div className="chart-panel" ref={ref} />;
}
