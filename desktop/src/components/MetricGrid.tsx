import StatusBadge from "./StatusBadge";

export type MetricItem = {
  label: string;
  value: string | number | boolean | null | undefined;
  tone?: "good" | "warn" | "bad" | "neutral";
};

function displayValue(value: MetricItem["value"]) {
  if (value === true) return "是";
  if (value === false) return "否";
  if (value === null || value === undefined || value === "") return "--";
  return String(value);
}

export default function MetricGrid({ items }: { items: MetricItem[] }) {
  return (
    <div className="metric-grid">
      {items.map((item) => (
        <div className="metric-card" key={item.label}>
          <span>{item.label}</span>
          <strong>{displayValue(item.value)}</strong>
          {item.tone ? <StatusBadge label={item.tone} tone={item.tone} /> : null}
        </div>
      ))}
    </div>
  );
}
