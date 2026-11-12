"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { FlaskConical, Upload } from "lucide-react";
import { api, Application, DemoCase, DocumentInfo, errorMessage, money } from "@/lib/api";
import { Badge, Card } from "@/components/ui";

const DOC_TYPES: [string, string][] = [
  ["", "Auto-detect"],
  ["sustainability_report", "Sustainability report"],
  ["energy_records", "Energy records"],
  ["production_data", "Production data"],
  ["financial_statement", "Financial statement"],
  ["other", "Other"],
];

const CASE_LABEL: Record<string, { label: string; tone: string }> = {
  case_b: { label: "Unsupported claim", tone: "amber" },
  case_f: { label: "Alternative explanation", tone: "blue" },
  case_a: { label: "Supported claims", tone: "green" },
  case_e: { label: "Incomplete application", tone: "slate" },
};
const CASE_ORDER = ["case_b", "case_f", "case_a", "case_e"];
const caseKey = (slug: string) => slug.slice(0, 6);

export default function NewInvestigation() {
  const router = useRouter();
  const [cases, setCases] = useState<DemoCase[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [org, setOrg] = useState({ name: "", sector: "", location: "" });
  const [project, setProject] = useState("");
  const [amount, setAmount] = useState("");
  const [files, setFiles] = useState<{ file: File; docType: string }[]>([]);

  useEffect(() => {
    api<DemoCase[]>("/demo/cases")
      .then((list) =>
        setCases([...list].sort((a, b) => CASE_ORDER.indexOf(caseKey(a.slug)) - CASE_ORDER.indexOf(caseKey(b.slug)))),
      )
      .catch(() => setCases([]));
  }, []);

  async function startInvestigation(applicationId: number) {
    setBusy("Starting the investigation...");
    await api(`/applications/${applicationId}/investigate`, { method: "POST" });
    router.push(`/investigations/${applicationId}`);
  }

  async function loadDemo(slug: string) {
    setError(null);
    setBusy("Loading demo documents...");
    try {
      const res = await api<{ application_id: number }>(`/demo/${slug}/load`, { method: "POST" });
      await startInvestigation(res.application_id);
    } catch (err) {
      setError(errorMessage(err));
      setBusy(null);
    }
  }

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setBusy("Creating the application...");
    try {
      const created = await api<Application>("/applications", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          organization: {
            name: org.name,
            sector: org.sector || null,
            location: org.location || null,
            country: "Pakistan",
          },
          title: `Green financing application - ${org.name}`,
          project_description: project || null,
          requested_amount: amount ? Number(amount) : null,
          currency: "PKR",
        }),
      });
      for (const item of files) {
        setBusy(`Uploading ${item.file.name}...`);
        const form = new FormData();
        form.append("file", item.file);
        if (item.docType) form.append("doc_type", item.docType);
        await api<DocumentInfo>(`/applications/${created.id}/documents`, { method: "POST", body: form });
      }
      await startInvestigation(created.id);
    } catch (err) {
      setError(errorMessage(err));
      setBusy(null);
    }
  }

  return (
    <div className="stack">
      <div className="page-head">
        <div>
          <h1 className="page-title">New investigation</h1>
          <p className="page-sub">Submit a financing application with supporting documents, or load a synthetic demo case.</p>
        </div>
      </div>

      {error && <div className="alert alert-error">{error}</div>}
      {busy && <div className="alert alert-info">{busy}</div>}

      <Card title="Demo cases" subtitle="Synthetic, fictional companies. One click loads the documents and runs the full investigation.">
        {cases.length === 0 ? (
          <p className="muted">No demo cases found. Make sure the backend is running and sample data has been generated.</p>
        ) : (
          <div className="grid-4">
            {cases.map((c) => {
              const meta = CASE_LABEL[caseKey(c.slug)] ?? { label: "Demo case", tone: "muted" };
              return (
                <div key={c.slug} className="list-item">
                  <Badge tone={meta.tone}>{meta.label}</Badge>
                  <div className="list-title" style={{ marginTop: 10 }}>{c.company}</div>
                  <div className="faint" style={{ margin: "4px 0 8px" }}>{c.location}</div>
                  <div className="muted" style={{ fontSize: 13 }}>{c.project}</div>
                  <div className="faint" style={{ margin: "8px 0 12px", fontSize: 12 }}>
                    {money(c.requested_amount_pkr, "PKR")} · {c.documents.length} document{c.documents.length === 1 ? "" : "s"}
                  </div>
                  <button className="btn btn-primary btn-sm" disabled={!!busy} onClick={() => loadDemo(c.slug)}>
                    <FlaskConical size={14} /> Load and investigate
                  </button>
                </div>
              );
            })}
          </div>
        )}
      </Card>

      <form onSubmit={submit} className="stack">
        <Card title="Business and project" subtitle="Basic details about the applicant and the financed project">
          <div className="grid-3">
            <div className="field">
              <label>Company name</label>
              <input className="input" required value={org.name} onChange={(e) => setOrg({ ...org, name: e.target.value })} />
            </div>
            <div className="field">
              <label>Sector</label>
              <input className="input" placeholder="e.g. Manufacturing - packaging" value={org.sector} onChange={(e) => setOrg({ ...org, sector: e.target.value })} />
            </div>
            <div className="field">
              <label>Plant location</label>
              <input className="input" placeholder="e.g. Korangi, Karachi" value={org.location} onChange={(e) => setOrg({ ...org, location: e.target.value })} />
            </div>
          </div>
          <div className="grid-2" style={{ marginTop: 16 }}>
            <div className="field">
              <label>Project description</label>
              <textarea className="textarea" placeholder="What will the financing be used for?" value={project} onChange={(e) => setProject(e.target.value)} />
            </div>
            <div className="field">
              <label>Requested amount (PKR)</label>
              <input className="input" type="number" min="0" value={amount} onChange={(e) => setAmount(e.target.value)} />
            </div>
          </div>
        </Card>

        <Card title="Documents" subtitle="PDF, CSV or TXT: financial statements, sustainability reports, energy and production records">
          <div className="drop">
            <Upload size={22} />
            <div style={{ margin: "8px 0" }}>Choose one or more files</div>
            <input
              type="file"
              multiple
              accept=".pdf,.csv,.txt"
              onChange={(e) =>
                setFiles(Array.from(e.target.files ?? []).map((file) => ({ file, docType: "" })))
              }
            />
          </div>
          {files.length > 0 && (
            <ul className="list" style={{ marginTop: 14 }}>
              {files.map((item, idx) => (
                <li key={item.file.name + idx} className="list-item row between">
                  <span>{item.file.name}</span>
                  <select
                    className="select"
                    style={{ width: 220 }}
                    value={item.docType}
                    onChange={(e) =>
                      setFiles(files.map((f, i) => (i === idx ? { ...f, docType: e.target.value } : f)))
                    }
                  >
                    {DOC_TYPES.map(([value, label]) => (
                      <option key={value} value={value}>
                        {label}
                      </option>
                    ))}
                  </select>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <div>
          <button className="btn btn-primary" type="submit" disabled={!!busy || !org.name}>
            Create and investigate
          </button>
        </div>
      </form>
    </div>
  );
}