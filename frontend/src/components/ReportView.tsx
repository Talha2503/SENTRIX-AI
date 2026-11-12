import type { Dimension, FindingEntry, ReportContent } from "@/lib/api";
import {
  Bar,
  Card,
  RISK_TONE,
  Ring,
  SeverityBadge,
  StatusBadge,
  VerifyBadge,
  pretty,
  toneForPct,
} from "./ui";

function FindingList({ items, empty }: { items: FindingEntry[]; empty: string }) {
  if (items.length === 0) return <p className="muted">{empty}</p>;
  return (
    <ul className="list">
      {items.map((f) => (
        <li key={f.id} className="list-item">
          <div className="list-title">{f.title}</div>
          <div className="badges">
            <SeverityBadge severity={f.severity} />
            <StatusBadge status={f.status} />
            <VerifyBadge status={f.verification_status} />
            <span className="chip">{pretty(f.agent)}</span>
          </div>
        </li>
      ))}
    </ul>
  );
}

function DimensionCard({ d }: { d: Dimension }) {
  const riskTone = RISK_TONE[d.risk_level] ?? "muted";
  const cov = d.coverage * 100;
  return (
    <Card title={d.label} right={<span className="chip">weight {Math.round(d.weight * 100)}%</span>}>
      <div className="metric" style={{ marginTop: 0 }}>
        <div className="metric-head">
          <span>Risk</span>
          <strong className={`tone-${riskTone} tone-text`}>
            {d.risk_score == null ? "Not assessed" : `${Math.round(d.risk_score)} · ${d.risk_level}`}
          </strong>
        </div>
        <Bar value={d.risk_score} tone={riskTone} />
      </div>
      <div className="metric">
        <div className="metric-head">
          <span>Evidence coverage</span>
          <strong>
            {Math.round(cov)}% · {d.reliability}
          </strong>
        </div>
        <Bar value={cov} tone={toneForPct(cov)} />
      </div>
      <div className="metric">
        <div className="metric-head">
          <span>Confidence</span>
          <strong>{d.confidence == null ? "n/a" : `${Math.round(d.confidence * 100)}%`}</strong>
        </div>
      </div>
      {d.basis.length > 0 && (
        <details>
          <summary>What drives this score</summary>
          <ul className="list">
            {d.basis.slice(0, 5).map((b, i) => (
              <li key={i} className="list-item" style={{ fontSize: 13 }}>
                {b.note ?? b.title}
                {b.points != null && <span className="faint"> (+{b.points} pts{b.verification ? `, ${b.verification}` : ""})</span>}
              </li>
            ))}
          </ul>
        </details>
      )}
    </Card>
  );
}

export default function ReportView({ content, reviewStatus }: { content: ReportContent; reviewStatus: string }) {
  const { overall } = content;
  const riskTone = RISK_TONE[overall.risk_level] ?? "muted";
  const cov = overall.coverage * 100;

  return (
    <div className="stack">
      <div className="grid-2" style={{ gridTemplateColumns: "minmax(0, 2fr) minmax(0, 1.2fr)" }}>
        <Card
          title="Executive summary"
          subtitle={`Review status: ${pretty(reviewStatus)}`}
          right={<span className="chip">{content.executive_summary_source === "llm" ? "Drafted by AI from verified facts" : "Template summary"}</span>}
        >
          <p className="pre" style={{ fontSize: 15, lineHeight: 1.65 }}>{content.executive_summary}</p>
        </Card>
        <Card title="Assessment at a glance" subtitle="Risk, coverage and confidence are reported separately">
          <div className="row" style={{ justifyContent: "space-around", alignItems: "flex-start" }}>
            <Ring
              value={overall.risk_score}
              label="Overall risk"
              sub={overall.risk_score == null ? "not given" : overall.risk_level}
              tone={riskTone}
            />
            <Ring value={cov} label="Coverage" sub={overall.reliability} tone={toneForPct(cov)} center={`${Math.round(cov)}%`} />
            <Ring
              value={overall.confidence == null ? null : overall.confidence * 100}
              label="Confidence"
              sub="of findings"
              tone="green"
              center={overall.confidence == null ? "n/a" : `${Math.round(overall.confidence * 100)}%`}
            />
          </div>
          {overall.risk_score == null && (
            <p className="muted" style={{ marginTop: 12, fontSize: 13 }}>
              No overall risk score is given because evidence coverage is too low. Missing information is not treated as risk.
            </p>
          )}
        </Card>
      </div>

      <div className="alert alert-note">{content.disclaimers.join(" ")}</div>

      <div className="grid-4">
        {Object.entries(content.dimensions).map(([key, d]) => (
          <DimensionCard key={key} d={d} />
        ))}
      </div>

      <div className="grid-2">
        <Card title="Issues for review" subtitle="Contradictions and anomalies. Alternative explanations are possible.">
          <FindingList items={content.issues_for_review} empty="No contradictions or anomalies were flagged." />
        </Card>
        <Card title="Unresolved questions" subtitle="Information is missing or claims remain unverified">
          <FindingList items={content.unresolved_questions} empty="No open questions." />
        </Card>
      </div>

      <div className="grid-2">
        <Card title="Supported findings" subtitle="The available evidence supports these within the stated scope">
          <FindingList items={content.supported_findings} empty="Nothing could be positively verified yet." />
        </Card>
        <Card title="Recommended follow-up evidence" subtitle="What to ask the applicant for next">
          {content.recommended_followups.length === 0 ? (
            <p className="muted">No follow-up requests.</p>
          ) : (
            <ul className="list">
              {content.recommended_followups.map((item, i) => (
                <li key={i} className="list-item">{item}</li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      <Card title="Limitations of this assessment">
        <ul className="list">
          {content.limitations.map((item, i) => (
            <li key={i} className="list-item muted">{item}</li>
          ))}
        </ul>
      </Card>
    </div>
  );
}