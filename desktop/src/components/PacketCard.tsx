import StatusBadge from "./StatusBadge";
import type { ReactNode } from "react";

type StatusTone = "good" | "warn" | "bad" | "neutral";

function statusTone(status?: string): StatusTone {
  const value = String(status ?? "").toLowerCase();
  if (!value) return "neutral";
  if (/(failed|error|blocked|expired|stale|denied|invalid|missing)/.test(value)) return "bad";
  if (/(pending|partial|review|warn|fallback|degraded|not_run|not_executed)/.test(value)) return "warn";
  if (/(ok|ready|passed|success|fresh|completed|available)/.test(value)) return "good";
  return "neutral";
}

export default function PacketCard({
  title,
  subtitle,
  status,
  children
}: {
  title: string;
  subtitle?: string;
  status?: string;
  children?: ReactNode;
}) {
  const tone = statusTone(status);
  return (
    <section
      className="packet-card motion-surface"
      data-motion-purpose="visual_hierarchy_clarity"
      data-motion-scope="packet_status_clarity"
      data-status-tone={tone}
    >
      <div className="packet-card-title">
        <div>
          <h3>{title}</h3>
          {subtitle ? <p>{subtitle}</p> : null}
        </div>
        {status ? <StatusBadge label={status} tone={tone} /> : null}
      </div>
      {children}
    </section>
  );
}
