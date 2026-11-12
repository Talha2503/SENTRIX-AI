"use client";

import { useState } from "react";
import { API_URL, DocumentInfo, Evidence, Finding } from "@/lib/api";
import { Card, SeverityBadge, StatusBadge, VerifyBadge, pretty } from "./ui";

const SEVERITY_RANK: Record<string, number> = { high: 0, medium: 1, low: 2 };

export default function FindingsView({
  findings,
  evidenceMap,
  docs,
}: {
  findings: Finding[];
  evidenceMap: Record<number, Evidence>;
  docs: Record<number, DocumentInfo>;
}) {
  const [status, setStatus] = useState("all");
  const [severity, setSeverity] = useState("all");

  const shown = findings
    .filter((f) => (status === "all" || f.status === status) && (severity === "all" || f.severity === severity))
    .sort((a, b) => (SEVERITY_RANK[a.severity] ?? 3) - (SEVERITY_RANK[b.severity] ?? 3) || a.id - b.id);

  return (
    <div className="stack">
      <div className="row">
        <select className="select" style={{ width: 220 }} value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="all">All statuses</option>
          <option value="contradictory">Contradictory</option>
          <option value="potential_anomaly">Potential anomaly</option>
          <option value="insufficient_information">Insufficient information</option>
          <option value="unverified">Unverified</option>
          <option value="verified">Supported</option>
          <option value="not_assessed">Not assessed</option>
        </select>
        <select className="select" style={{ width: 180 }} value={severity} onChange={(e) => setSeverity(e.target.value)}>
          <option value="all">All severities</option>
          <option value="high">High</option>
          <option value="medium">Medium</option>
          <option value="low">Low</option>
        </select>
        <span className="muted">{shown.length} of {findings.length} findings</span>
      </div>

      {shown.map((f) => (
        <Card key={f.id}>
          <div className="row between" style={{ alignItems: "flex-start" }}>
            <div style={{ flex: 1, minWidth: 260 }}>
              <h3 className="card-title" style={{ fontSize: 16 }}>{f.title}</h3>
              <div className="badges">
                <SeverityBadge severity={f.severity} />
                <StatusBadge status={f.status} />
                <VerifyBadge status={f.verification_status} />
                <span className="chip">{pretty(f.agent_name)}</span>
                {f.confidence != null && <span className="chip">confidence {Math.round(f.confidence * 100)}%</span>}
              </div>
            </div>
          </div>

          <details>
            <summary>Explanation and verification</summary>
            <p className="pre" style={{ lineHeight: 1.6 }}>{f.explanation}</p>
            {f.confidence_notes && <p className="faint" style={{ marginTop: 8, fontSize: 12 }}>Confidence basis: {f.confidence_notes}</p>}
          </details>

          {f.recommended_followup && (
            <p style={{ marginTop: 10 }}>
              <strong className="tone-green tone-text">Follow-up: </strong>
              <span className="muted">{f.recommended_followup}</span>
            </p>
          )}

          {f.evidence_ids.length > 0 && (
            <details>
              <summary>Evidence ({f.evidence_ids.length})</summary>
              <ul className="list">
                {f.evidence_ids.map((id) => {
                  const e = evidenceMap[id];
                  if (!e) return null;
                  const doc = e.document_id != null ? docs[e.document_id] : undefined;
                  return (
                    <li key={id} className="list-item" style={{ fontSize: 13 }}>
                      <div className="row between">
                        <span>
                          <span className="chip">{pretty(e.evidence_type)}</span>{" "}
                          {e.metric && <strong>{e.metric}</strong>}
                          {e.value != null && ` = ${e.value.toLocaleString()} ${e.unit ?? ""}`}
                          {e.reporting_period && <span className="faint"> ({e.reporting_period})</span>}
                        </span>
                        {doc && (
                          <a
                            className="tone-green tone-text"
                            href={`${API_URL}/documents/${doc.id}/file${e.page_number ? `#page=${e.page_number}` : ""}`}
                            target="_blank"
                            rel="noreferrer"
                          >
                            {doc.filename}{e.page_number ? ` p.${e.page_number}` : ""}
                          </a>
                        )}
                      </div>
                      {e.excerpt && <div className="quote">{e.excerpt}</div>}
                    </li>
                  );
                })}
              </ul>
            </details>
          )}
        </Card>
      ))}
      {shown.length === 0 && <div className="empty">No findings match the filters.</div>}
    </div>
  );
}