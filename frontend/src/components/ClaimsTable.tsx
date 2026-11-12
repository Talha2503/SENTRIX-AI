"use client";

import { Fragment, useState } from "react";
import type { Claim, DocumentInfo, Finding } from "@/lib/api";
import { Badge, Card, SeverityBadge, StatusBadge, VerifyBadge, pretty } from "./ui";

export default function ClaimsTable({
  claims,
  findings,
  docs,
}: {
  claims: Claim[];
  findings: Finding[];
  docs: Record<number, DocumentInfo>;
}) {
  const [open, setOpen] = useState<number | null>(null);

  return (
    <Card title="Claim verification" subtitle="Every claim keeps the quote it came from. Click a row to see the findings linked to it.">
      {claims.length === 0 ? (
        <div className="empty">No claims were extracted.</div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Claim</th>
                <th>Category</th>
                <th>Value</th>
                <th>Baseline</th>
                <th>Source</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {claims.map((c) => {
                const linked = findings.filter((f) => f.claim_id === c.id);
                return (
                  <Fragment key={c.id}>
                    <tr className="clickable" onClick={() => setOpen(open === c.id ? null : c.id)}>
                      <td style={{ maxWidth: 380 }}>
                        <strong>{c.claim_text}</strong>
                      </td>
                      <td>
                        <Badge tone="muted">{pretty(c.category)}</Badge>
                      </td>
                      <td>{c.value == null ? <span className="faint">-</span> : `${c.value}${c.unit ?? ""}`}</td>
                      <td>{c.baseline_period ?? <span className="faint">not stated</span>}</td>
                      <td className="muted">
                        {c.document_id != null ? docs[c.document_id]?.filename ?? `doc ${c.document_id}` : "-"}
                        {c.page_number != null && ` · p.${c.page_number}`}
                      </td>
                      <td>
                        <StatusBadge status={c.status} />
                      </td>
                    </tr>
                    {open === c.id && (
                      <tr>
                        <td colSpan={6} style={{ background: "rgba(5,20,15,0.5)" }}>
                          {c.source_quote && <p className="quote">&ldquo;{c.source_quote}&rdquo;</p>}
                          <div className="faint" style={{ margin: "6px 0 10px", fontSize: 12 }}>
                            Extracted by {c.extraction_method ?? "unknown"}; reporting period: {c.reporting_period ?? "not stated"}
                          </div>
                          {linked.length === 0 ? (
                            <p className="muted">No findings are linked to this claim.</p>
                          ) : (
                            <ul className="list">
                              {linked.map((f) => (
                                <li key={f.id} className="list-item">
                                  <div className="list-title">{f.title}</div>
                                  <div className="badges">
                                    <SeverityBadge severity={f.severity} />
                                    <StatusBadge status={f.status} />
                                    <VerifyBadge status={f.verification_status} />
                                  </div>
                                </li>
                              ))}
                            </ul>
                          )}
                        </td>
                      </tr>
                    )}
                  </Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}