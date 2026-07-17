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

function toneLabel(tone: NonNullable<MetricItem["tone"]>) {
  if (tone === "good") return "状态正常";
  if (tone === "warn") return "需要留意";
  if (tone === "bad") return "存在阻断";
  return "状态中性";
}

function toneIcon(tone: NonNullable<MetricItem["tone"]>) {
  if (tone === "good") return "✓";
  if (tone === "warn") return "!";
  if (tone === "bad") return "×";
  return "•";
}

export default function MetricGrid({ items }: { items: MetricItem[] }) {
  return (
    <div className="metric-grid">
      {items.map((item, index) => (
        <div
          className="metric-card motion-surface"
          data-metric-tone={item.tone ?? "neutral"}
          data-motion-purpose="visual_hierarchy_clarity"
          key={`${item.label}-${index}`}
          role="group"
          aria-label={`${item.label}，${toneLabel(item.tone ?? "neutral")}`}
          style={{ "--motion-delay": `${Math.min(index, 8) * 24}ms` } as CSSProperties}
        >
          <span className="metric-card__label">{item.label}</span>
          <strong>{displayValue(item.value)}</strong>
          {item.tone ? (
            <span className="metric-card__tone" aria-hidden="true" title={toneLabel(item.tone)}>
              {toneIcon(item.tone)}
            </span>
          ) : null}
        </div>
      ))}
    </div>
  );
}
