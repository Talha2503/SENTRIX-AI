import { CheckCircle2, Circle, Loader2, XCircle } from "lucide-react";
import { duration, Investigation } from "@/lib/api";
import { Card, Ring, pretty } from "./ui";

function highlights(output: Record<string, unknown> | null): string[] {
  if (!output) return [];
  const out: string[] = [];
  for (const [key, value] of Object.entries(output)) {
    if (typeof value === "number" || typeof value === "boolean") out.push(`${pretty(key)}: ${String(value)}`);
    else if (typeof value === "string" && value.length < 40) out.push(`${pretty(key)}: ${value}`);
    else if (Array.isArray(value)) out.push(`${pretty(key)}: ${value.length}`);
    if (out.length >= 6) break;
  }
  return out;
}

export default function AgentMonitor({ inv }: { inv: Investigation }) {
  const runs = inv.agent_runs;
  const done = runs.filter((r) => r.status === "completed").length;
  const failed = runs.filter((r) => r.status === "failed").length;
  const running = inv.status === "investigating";

  return (
    <div className="stack">
      <div className="grid-4">
        <Card>
          <Ring
            value={runs.length ? (done / runs.length) * 100 : 0}
            label="Agent tasks"
            sub={running ? "in progress" : "finished"}
            tone={failed ? "red" : "green"}
            center={`${done}/${runs.length}`}
          />
        </Card>
        <div className="card kpi">
          <div className="kpi-label">Claims extracted</div>
          <div className="kpi-value">{inv.claim_count}</div>
          <div className="kpi-sub">with source quotes</div>
        </div>
        <div className="card kpi">
          <div className="kpi-label">Evidence items</div>
          <div className="kpi-value">{inv.evidence_count}</div>
          <div className="kpi-sub">traceable to a document or calculation</div>
        </div>
        <div className="card kpi">
          <div className="kpi-label">Failed tasks</div>
          <div className="kpi-value">{failed}</div>
          <div className="kpi-sub">{failed ? "see errors below" : "none"}</div>
        </div>
      </div>

      <Card title="Activity timeline" subtitle="Each agent task, in the order it ran">
        {runs.length === 0 ? (
          <p className="muted">Waiting for the first task...</p>
        ) : (
          <div className="timeline">
            {runs.map((r) => {
              const tone = r.status === "completed" ? "green" : r.status === "failed" ? "red" : r.status === "running" ? "blue" : "muted";
              const Icon = r.status === "completed" ? CheckCircle2 : r.status === "failed" ? XCircle : r.status === "running" ? Loader2 : Circle;
              return (
                <div key={r.id} className={`tl-item tone-${tone}`}>
                  <div className="tl-dot">
                    <Icon size={18} className={r.status === "running" ? "spin" : ""} />
                  </div>
                  <div>
                    <div className="tl-title">{pretty(r.agent_name)}</div>
                    <div className="tl-meta">
                      {r.task} {duration(r.started_at, r.finished_at) && `· ${duration(r.started_at, r.finished_at)}`}
                    </div>
                    {r.error && <div className="alert alert-error" style={{ marginTop: 8 }}>{r.error}</div>}
                    <div className="badges">
                      {highlights(r.output).map((h) => (
                        <span key={h} className="chip">{h}</span>
                      ))}
                    </div>
                    {r.output && (
                      <details>
                        <summary>Raw output</summary>
                        <pre className="mono pre muted">{JSON.stringify(r.output, null, 2)}</pre>
                      </details>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </Card>
    </div>
  );
}