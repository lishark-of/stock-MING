import StatusBadge from "./StatusBadge";
import type { CSSProperties } from "react";

export type MetricItem = {
  label: string;
  value: unknown;
  tone?: "good" | "warn" | "bad" | "neutral";
};

function displayValue(value: MetricItem["value"]) {
  if (value === true) return "是";
  if (value === false) return "否";
  if (value === null || value === undefined || value === "") return "--";
  if (Array.isArray(value) || typeof value === "object") {
    try {
      return JSON.stringify(value);
    } catch {
      return "[结构化数据]";
    }
  }
  return String(value);
}

export default function MetricGrid({ items }: { items: MetricItem[] }) {
  return (
    <div className="metric-grid">
      {items.map((item, index) => (
        <div
          className="metric-card motion-surface"
          key={item.label}
          style={{ "--motion-delay": `${Math.min(index, 8) * 24}ms` } as CSSProperties}
        >
          <span>{item.label}</span>
          <strong>{displayValue(item.value)}</strong>
          {item.tone ? <StatusBadge label={item.tone} tone={item.tone} /> : null}
        </div>
      ))}
    </div>
  );
}
