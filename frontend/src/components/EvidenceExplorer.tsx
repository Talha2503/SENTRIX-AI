"use client";

import { useMemo, useState } from "react";
import { API_URL, DocumentInfo, Evidence, Finding } from "@/lib/api";
import { Card, pretty } from "./ui";

export default function EvidenceExplorer({
  evidence,
  findings,
  docs,
}: {
  evidence: Evidence[];
  findings: Finding[];
  docs: Record<number, DocumentInfo>;
}) {
  const [doc, setDoc] = useState("all");
  const [type, setType] = useState("all");
  const [query, setQuery] = useState("");

  const usedBy = useMemo(() => {
    const map: Record<number, Finding[]> = {};
    for (const f of findings) for (const id of f.evidence_ids) (map[id] ??= []).push(f);
    return map;
  }, [findings]);

  const types = useMemo(() => Array.from(new Set(evidence.map((e) => e.evidence_type))), [evidence]);
  const shown = evidence.filter((e) => {
    if (doc !== "all" && String(e.document_id) !== doc) return false;
    if (type !== "all" && e.evidence_type !== type) return false;
    const q = query.trim().toLowerCase();
    return !q || `${e.metric ?? ""} ${e.excerpt ?? ""} ${e.reporting_period ?? ""}`.toLowerCase().includes(q);
  });

  return (
    <Card title="Evidence explorer" subtitle="Source passages, extracted figures and calculations, with the findings that rely on them">
      <div className="row" style={{ marginBottom: 14 }}>
        <select className="select" style={{ width: 240 }} value={doc} onChange={(e) => setDoc(e.target.value)}>
          <option value="all">All documents</option>
          {Object.values(docs).map((d) => (
            <option key={d.id} value={d.id}>{d.filename}</option>
          ))}
        </select>
        <select className="select" style={{ width: 200 }} value={type} onChange={(e) => setType(e.target.value)}>
          <option value="all">All evidence types</option>
          {types.map((t) => (
            <option key={t} value={t}>{pretty(t)}</option>
          ))}
        </select>
        <input className="input" style={{ width: 240 }} placeholder="Search metric or text" value={query} onChange={(e) => setQuery(e.target.value)} />
        <span className="muted">{shown.length} of {evidence.length}</span>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Type</th>
              <th>Metric / value</th>
              <th>Period</th>
              <th>Source</th>
              <th>Passage</th>
              <th>Used by</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((e) => {
              const d = e.document_id != null ? docs[e.document_id] : undefined;
              return (
                <tr key={e.id}>
                  <td><span className="chip">{pretty(e.evidence_type)}</span></td>
                  <td>
                    {e.metric && <strong>{e.metric}</strong>}
                    {e.value != null && <div>{e.value.toLocaleString()} {e.unit ?? ""}</div>}
                  </td>
                  <td className="muted">{e.reporting_period ?? "-"}</td>
                  <td>
                    {d ? (
                      <a
                        className="tone-green tone-text"
                        href={`${API_URL}/documents/${d.id}/file${e.page_number ? `#page=${e.page_number}` : ""}`}
                        target="_blank"
                        rel="noreferrer"
                      >
                        {d.filename}
                        {e.page_number ? ` · p.${e.page_number}` : ""}
                      </a>
                    ) : (
                      <span className="faint">{pretty(e.extraction_method ?? "calculation")}</span>
                    )}
                  </td>
                  <td style={{ maxWidth: 360 }} className="muted">{e.excerpt}</td>
                  <td className="muted">{usedBy[e.id]?.length ? `${usedBy[e.id].length} finding(s)` : "-"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Card>
  );
}