import StatusBadge from "./StatusBadge";
import type { ReactNode } from "react";

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
  return (
    <section className="packet-card">
      <div className="packet-card-title">
        <div>
          <h3>{title}</h3>
          {subtitle ? <p>{subtitle}</p> : null}
        </div>
        {status ? <StatusBadge label={status} tone={status === "ok" || status === "ready" ? "good" : "neutral"} /> : null}
      </div>
      {children}
    </section>
  );
}
