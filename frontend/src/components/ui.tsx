import type { ReactNode } from "react";

type Meta = { label: string; tone: string };

export const STATUS_META: Record<string, Meta> = {
  verified: { label: "Supported", tone: "green" },
  unverified: { label: "Unverified", tone: "slate" },
  contradictory: { label: "Contradictory", tone: "red" },
  potential_anomaly: { label: "Potential anomaly", tone: "amber" },
  insufficient_information: { label: "Insufficient information", tone: "blue" },
  not_assessed: { label: "Not assessed", tone: "muted" },
};

export const VERIFY_META: Record<string, Meta> = {
  verified: { label: "Stands after challenge", tone: "green" },
  disputed: { label: "Disputed: alternative supported", tone: "amber" },
  unresolved: { label: "Unresolved", tone: "blue" },
  unsupported: { label: "Evidence untraceable", tone: "red" },
  not_challenged: { label: "Not challenged", tone: "muted" },
  pending: { label: "Pending", tone: "muted" },
};

export const APP_STATUS_META: Record<string, Meta> = {
  draft: { label: "Draft", tone: "slate" },
  investigating: { label: "Investigating", tone: "blue" },
  completed: { label: "Completed", tone: "green" },
  analysed: { label: "Analysed", tone: "green" },
  extracted: { label: "Extracted", tone: "green" },
  failed: { label: "Failed", tone: "red" },
};

export const SEVERITY_TONE: Record<string, string> = { high: "red", medium: "amber", low: "slate" };
export const RISK_TONE: Record<string, string> = {
  low: "green",
  moderate: "amber",
  elevated: "orange",
  high: "red",
  "not assessed": "muted",
};

export function pretty(text: string): string {
  const spaced = text.replace(/_/g, " ");
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

export function toneForPct(p: number): string {
  if (p >= 75) return "green";
  if (p >= 50) return "amber";
  if (p >= 25) return "orange";
  return "red";
}

export function Badge({ tone = "muted", children }: { tone?: string; children: ReactNode }) {
  return <span className={`badge tone-${tone}`}>{children}</span>;
}

function metaBadge(map: Record<string, Meta>, key: string) {
  const meta = map[key] ?? { label: pretty(key), tone: "muted" };
  return <Badge tone={meta.tone}>{meta.label}</Badge>;
}

export function StatusBadge({ status }: { status: string }) {
  return metaBadge(STATUS_META, status);
}
export function VerifyBadge({ status }: { status: string }) {
  return metaBadge(VERIFY_META, status);
}
export function AppStatusBadge({ status }: { status: string }) {
  return metaBadge(APP_STATUS_META, status);
}
export function SeverityBadge({ severity }: { severity: string }) {
  return <Badge tone={SEVERITY_TONE[severity] ?? "muted"}>{pretty(severity)} severity</Badge>;
}

export function Card({
  title,
  subtitle,
  right,
  children,
  className = "",
}: {
  title?: string;
  subtitle?: string;
  right?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`card ${className}`}>
      {(title || right) && (
        <header className="card-head">
          <div>
            {title && <h3 className="card-title">{title}</h3>}
            {subtitle && <p className="card-sub">{subtitle}</p>}
          </div>
          {right}
        </header>
      )}
      <div className="card-body">{children}</div>
    </section>
  );
}

export function Ring({
  value,
  label,
  sub,
  tone = "green",
  size = 116,
  center,
}: {
  value: number | null;
  label: string;
  sub?: string;
  tone?: string;
  size?: number;
  center?: string;
}) {
  const stroke = 9;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const pct = value == null ? 0 : Math.max(0, Math.min(100, value));
  return (
    <div className={`ring tone-${tone}`}>
      <div className="ring-svg" style={{ width: size, height: size }}>
        <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
          <circle cx={size / 2} cy={size / 2} r={r} className="ring-track" strokeWidth={stroke} fill="none" />
          <circle
            cx={size / 2}
            cy={size / 2}
            r={r}
            className="ring-value"
            strokeWidth={stroke}
            fill="none"
            strokeLinecap="round"
            strokeDasharray={c}
            strokeDashoffset={c * (1 - pct / 100)}
            transform={`rotate(-90 ${size / 2} ${size / 2})`}
          />
        </svg>
        <div className="ring-center">
          <span className="ring-num">{center ?? (value == null ? "n/a" : Math.round(value))}</span>
        </div>
      </div>
      <div className="ring-label">{label}</div>
      {sub && <div className="ring-sub">{sub}</div>}
    </div>
  );
}

export function Bar({ value, tone = "green" }: { value: number | null; tone?: string }) {
  const pct = value == null ? 0 : Math.max(0, Math.min(100, value));
  return (
    <div className={`bar tone-${tone}`}>
      <div className="bar-fill" style={{ width: `${pct}%` }} />
    </div>
  );
}