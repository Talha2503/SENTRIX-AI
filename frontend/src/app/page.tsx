"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { ArrowRight, FilePlus2 } from "lucide-react";
import { api, Application, errorMessage, formatDate, money, Report } from "@/lib/api";
import { AppStatusBadge, Badge, Card, RISK_TONE, pretty } from "@/components/ui";

export default function Dashboard() {
  const [apps, setApps] = useState<Application[] | null>(null);
  const [reports, setReports] = useState<Record<number, Report | null>>({});
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const list = await api<Application[]>("/applications");
      setApps(list);
      const entries = await Promise.all(
        list
          .filter((a) => a.status === "completed")
          .map(async (a) => {
            try {
              return [a.id, await api<Report>(`/applications/${a.id}/report`)] as const;
            } catch {
              return [a.id, null] as const;
            }
          }),
      );
      setReports(Object.fromEntries(entries));
      setError(null);
    } catch (err) {
      setError(errorMessage(err));
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (apps?.some((a) => a.status === "investigating")) {
      const timer = setTimeout(load, 4000);
      return () => clearTimeout(timer);
    }
  }, [apps, load]);

  const done = Object.values(reports).filter((r): r is Report => r !== null);
  const flagged = done.reduce((n, r) => n + r.content.issues_for_review.length, 0);
  const avgCoverage = done.length ? (done.reduce((n, r) => n + r.content.overall.coverage, 0) / done.length) * 100 : null;

  return (
    <div className="stack">
      <div className="page-head">
        <div>
          <h1 className="page-title">Dashboard</h1>
          <p className="page-sub">Evidence-based green-finance due diligence: investigations and their status.</p>
        </div>
        <Link href="/new" className="btn btn-primary">
          <FilePlus2 size={18} /> New investigation
        </Link>
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      <div className="grid-4">
        <div className="card kpi">
          <div className="kpi-label">Investigations</div>
          <div className="kpi-value">{apps?.length ?? "-"}</div>
          <div className="kpi-sub">{apps ? `${apps.filter((a) => a.status === "investigating").length} running` : ""}</div>
        </div>
        <div className="card kpi">
          <div className="kpi-label">Completed reports</div>
          <div className="kpi-value">{done.length}</div>
          <div className="kpi-sub">ready for human review</div>
        </div>
        <div className="card kpi">
          <div className="kpi-label">Items flagged for review</div>
          <div className="kpi-value">{flagged}</div>
          <div className="kpi-sub">contradictions and anomalies</div>
        </div>
        <div className="card kpi">
          <div className="kpi-label">Average evidence coverage</div>
          <div className="kpi-value">{avgCoverage == null ? "-" : `${Math.round(avgCoverage)}%`}</div>
          <div className="kpi-sub">across completed reports</div>
        </div>
      </div>

      <Card title="Investigations" subtitle="Most recent first">
        {apps && apps.length === 0 ? (
          <div className="empty">
            <p>No investigations yet.</p>
            <p style={{ marginTop: 12 }}>
              <Link href="/new" className="btn btn-primary">
                Start with a demo case
              </Link>
            </p>
          </div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Company</th>
                  <th>Project</th>
                  <th>Requested</th>
                  <th>Status</th>
                  <th>Risk</th>
                  <th>Coverage</th>
                  <th>Created</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {(apps ?? []).map((a) => {
                  const report = reports[a.id];
                  const overall = report?.content.overall;
                  return (
                    <tr key={a.id}>
                      <td>
                        <strong>{a.organization.name}</strong>
                        <div className="faint">{a.organization.location}</div>
                      </td>
                      <td style={{ maxWidth: 280 }}>{a.project_description ?? "-"}</td>
                      <td>{money(a.requested_amount, a.currency)}</td>
                      <td>
                        <AppStatusBadge status={a.status} />
                      </td>
                      <td>
                        {overall ? (
                          <Badge tone={RISK_TONE[overall.risk_level] ?? "muted"}>
                            {overall.risk_score == null ? "Not given" : `${Math.round(overall.risk_score)} · ${pretty(overall.risk_level)}`}
                          </Badge>
                        ) : (
                          <span className="faint">-</span>
                        )}
                      </td>
                      <td>{overall ? `${Math.round(overall.coverage * 100)}%` : <span className="faint">-</span>}</td>
                      <td className="muted">{formatDate(a.created_at)}</td>
                      <td>
                        <Link href={`/investigations/${a.id}`} className="btn btn-sm">
                          Open <ArrowRight size={14} />
                        </Link>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}