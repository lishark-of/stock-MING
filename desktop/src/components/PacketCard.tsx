import type { ReactNode } from "react";

type StatusTone = "good" | "warn" | "bad" | "neutral";

export function statusTone(status?: string): StatusTone {
  const value = String(status ?? "").toLowerCase();
  if (!value) return "neutral";
  const tokens = value.split(/[^a-z0-9]+/).filter(Boolean);
  const explicitlyNegatedPositive =
    /(?:^|[_\s-])not[_\s-]?(?:ok|ready|available|completed|passed|success|successful|fresh|verified)(?:$|[_\s-])/.test(value) ||
    tokens.some((token) => ["notready", "unready", "unavailable", "incomplete", "unsuccessful", "unverified"].includes(token));
  if (explicitlyNegatedPositive) return "bad";
  const negatedNegativePattern = /(?:^|[_\s-])(?:not|no)[_\s-]?(?:blocked|blocker|blockers|failed|failure|error|errors|missing|unsafe|stale|denied|invalid|rejected)(?:$|[_\s-])/g;
  const explicitlyNegatedNegative = negatedNegativePattern.test(value);
  const remainingValue = value.replace(negatedNegativePattern, " ");
  const remainingTokens = remainingValue.split(/[^a-z0-9]+/).filter(Boolean);
  if (remainingTokens.some((token) => ["failed", "failure", "error", "blocked", "blocker", "blockers", "expired", "stale", "denied", "invalid", "missing", "rejected", "unsafe"].includes(token))) return "bad";
  if (/(pending|partial|review|warn|fallback|degraded|not_run|not_executed)/.test(remainingValue)) return "warn";
  if (explicitlyNegatedNegative) return "good";
  if (remainingTokens.some((token) => ["ok", "ready", "passed", "success", "fresh", "completed", "available", "verified"].includes(token))) return "good";
  return "neutral";
}

function toneLabel(tone: StatusTone) {
  if (tone === "good") return "状态正常";
  if (tone === "warn") return "需要留意";
  if (tone === "bad") return "存在阻断";
  return "状态信息";
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
        {status ? (
          <span className="packet-card__state" role="status" aria-label={`状态：${status}`} title={toneLabel(tone)}>
            <span className="packet-card__state-dot" aria-hidden="true" />
          </span>
        ) : null}
      </div>
      {children}
    </section>
  );
}
