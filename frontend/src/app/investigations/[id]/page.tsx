"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { Download, Printer, RefreshCw } from "lucide-react";
import {
  API_URL,
  api,
  Application,
  Claim,
  errorMessage,
  Evidence,
  Finding,
  formatDate,
  Investigation,
  money,
  Report,
} from "@/lib/api";
import AgentMonitor from "@/components/AgentMonitor";
import ClaimsTable from "@/components/ClaimsTable";
import EvidenceExplorer from "@/components/EvidenceExplorer";
import FindingsView from "@/components/FindingsView";
import ReportView from "@/components/ReportView";
import { AppStatusBadge, Card, pretty } from "@/components/ui";

type TabKey = "report" | "agents" | "claims" | "findings" | "evidence" | "documents";

export default function InvestigationPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;

  const [app, setApp] = useState<Application | null>(null);
  const [inv, setInv] = useState<Investigation | null>(null);
  const [report, setReport] = useState<Report | null>(null);
  const [claims, setClaims] = useState<Claim[]>([]);
  const [findings, setFindings] = useState<Finding[]>([]);
  const [evidence, setEvidence] = useState<Evidence[]>([]);
  const [tab, setTab] = useState<TabKey>("agents");
  const [error, setError] = useState<string | null>(null);
  const shownReport = useRef(false);

  const loadAll = useCallback(async () => {
    try {
      const [a, i] = await Promise.all([
        api<Application>(`/applications/${id}`),
        api<Investigation>(`/applications/${id}/investigation`),
      ]);
      setApp(a);
      setInv(i);
      if (i.status !== "investigating") {
        const [c, f, e, r] = await Promise.all([
          api<Claim[]>(`/applications/${id}/claims`),
          api<Finding[]>(`/applications/${id}/findings`),
          api<Evidence[]>(`/applications/${id}/evidence`),
          api<Report>(`/applications/${id}/report`).catch(() => null),
        ]);
        setClaims(c);
        setFindings(f);
        setEvidence(e);
        setReport(r);
      }
      setError(null);
    } catch (err) {
      setError(errorMessage(err));
    }
  }, [id]);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  useEffect(() => {
    if (inv?.status === "investigating") {
      const timer = setTimeout(loadAll, 2500);
      return () => clearTimeout(timer);
    }
  }, [inv, loadAll]);

  useEffect(() => {
    if (report && !shownReport.current) {
      shownReport.current = true;
      setTab("report");
    }
  }, [report]);

  const docs = useMemo(() => Object.fromEntries((app?.documents ?? []).map((d) => [d.id, d])), [app]);
  const evidenceMap = useMemo(() => Object.fromEntries(evidence.map((e) => [e.id, e])), [evidence]);

  async function rerun() {
    try {
      shownReport.current = false;
      setReport(null);
      await api(`/applications/${id}/investigate?force=true`, { method: "POST" });
      setTab("agents");
      await loadAll();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  function downloadJSON() {
    if (!report) return;
    const blob = new Blob([JSON.stringify(report.content, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `sentrix-report-${id}.json`;
    link.click();
    URL.revokeObjectURL(url);
  }

  const running = inv?.status === "investigating";
  const TABS: [TabKey, string, number | null][] = [
    ["report", "Report", null],
    ["agents", "Agent monitor", null],
    ["claims", "Claims", claims.length],
    ["findings", "Findings", findings.length],
    ["evidence", "Evidence", evidence.length],
    ["documents", "Documents", app?.documents.length ?? 0],
  ];

  return (
    <div className="stack">
      <div className="page-head">
        <div>
          <div className="crumbs">
            <Link href="/">Dashboard</Link> / Investigation #{id}
          </div>
          <h1 className="page-title">{app?.organization.name ?? "Loading..."}</h1>
          <p className="page-sub">
            {app?.project_description}
            {app && ` · ${money(app.requested_amount, app.currency)} requested`}
            {app?.organization.location && ` · ${app.organization.location}`}
          </p>
        </div>
        <div className="row no-print">
          {app && <AppStatusBadge status={app.status} />}
          <button className="btn btn-sm" onClick={rerun} disabled={running}>
            <RefreshCw size={14} className={running ? "spin" : ""} /> Re-run
          </button>
          <button className="btn btn-sm" onClick={downloadJSON} disabled={!report}>
            <Download size={14} /> JSON
          </button>
          <button className="btn btn-primary btn-sm" onClick={() => window.print()} disabled={!report}>
            <Printer size={14} /> Print / PDF
          </button>
        </div>
      </div>

      {error && <div className="alert alert-error">{error}</div>}
      {running && (
        <div className="alert alert-info">
          The investigation is running. Agents work in parallel, then a verification step challenges the findings. This page updates automatically.
        </div>
      )}
      {inv && !running && !report && (
        <div className="alert alert-error">
          No report was produced. Check the Agent monitor for errors, then press Re-run.
        </div>
      )}

      <div className="tabs no-print">
        {TABS.map(([key, label, count]) => (
          <button key={key} className={`tab ${tab === key ? "active" : ""}`} onClick={() => setTab(key)}>
            {label}
            {count != null && <small>{count}</small>}
          </button>
        ))}
      </div>

      {tab === "report" &&
        (report ? (
          <ReportView content={report.content} reviewStatus={report.review_status} />
        ) : (
          <div className="empty card">The report appears here when the investigation finishes.</div>
        ))}
      {tab === "agents" && inv && <AgentMonitor inv={inv} />}
      {tab === "claims" && <ClaimsTable claims={claims} findings={findings} docs={docs} />}
      {tab === "findings" && <FindingsView findings={findings} evidenceMap={evidenceMap} docs={docs} />}
      {tab === "evidence" && <EvidenceExplorer evidence={evidence} findings={findings} docs={docs} />}
      {tab === "documents" && (
        <Card title="Submitted documents" subtitle="Original files, kept unchanged">
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>File</th>
                  <th>Type</th>
                  <th>Pages</th>
                  <th>Processing</th>
                  <th>Uploaded</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {(app?.documents ?? []).map((d) => (
                  <tr key={d.id}>
                    <td><strong>{d.filename}</strong></td>
                    <td className="muted">{pretty(d.doc_type)}</td>
                    <td className="muted">{d.page_count ?? "-"}</td>
                    <td>
                      {d.status}
                      {d.error && <div className="faint">{d.error}</div>}
                    </td>
                    <td className="muted">{formatDate(d.uploaded_at)}</td>
                    <td>
                      <a className="btn btn-sm" href={`${API_URL}/documents/${d.id}/file`} target="_blank" rel="noreferrer">
                        Open
                      </a>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}