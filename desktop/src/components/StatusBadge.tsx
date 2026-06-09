export default function StatusBadge({ label, tone = "neutral" }: { label: string; tone?: "good" | "warn" | "bad" | "neutral" }) {
  return <span className={`status-badge status-${tone}`}>{label}</span>;
}
