export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, { cache: "no-store", ...init });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail ?? body);
    } catch {
      /* keep the status text */
    }
    throw new ApiError(detail, res.status);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export function errorMessage(err: unknown): string {
  if (err instanceof ApiError) return err.message;
  if (err instanceof TypeError) return "Cannot reach the backend. Is it running on port 8000?";
  return err instanceof Error ? err.message : "Something went wrong";
}

export interface Organization {
  id: number;
  name: string;
  sector: string | null;
  location: string | null;
  country: string;
  description: string | null;
  created_at: string;
}

export interface DocumentInfo {
  id: number;
  application_id: number;
  filename: string;
  doc_type: string;
  mime_type: string | null;
  page_count: number | null;
  status: string;
  error: string | null;
  uploaded_at: string;
}

export interface Application {
  id: number;
  title: string;
  project_description: string | null;
  requested_amount: number | null;
  currency: string;
  status: string;
  created_at: string;
  updated_at: string;
  organization: Organization;
  documents: DocumentInfo[];
}

export interface AgentRun {
  id: number;
  agent_name: string;
  task: string | null;
  status: string;
  error: string | null;
  output: Record<string, unknown> | null;
  started_at: string | null;
  finished_at: string | null;
}

export interface Investigation {
  application_id: number;
  status: string;
  claim_count: number;
  evidence_count: number;
  agent_runs: AgentRun[];
}

export interface Claim {
  id: number;
  document_id: number | null;
  chunk_id: number | null;
  claim_text: string;
  source_quote: string | null;
  category: string;
  value: number | null;
  unit: string | null;
  reporting_period: string | null;
  baseline_period: string | null;
  page_number: number | null;
  status: string;
  extraction_method: string | null;
}

export interface Finding {
  id: number;
  claim_id: number | null;
  agent_name: string;
  category: string;
  title: string;
  explanation: string;
  severity: string;
  status: string;
  verification_status: string;
  confidence: number | null;
  confidence_notes: string | null;
  recommended_followup: string | null;
  evidence_ids: number[];
}

export interface Evidence {
  id: number;
  document_id: number | null;
  chunk_id: number | null;
  claim_id: number | null;
  page_number: number | null;
  excerpt: string | null;
  evidence_type: string;
  metric: string | null;
  value: number | null;
  unit: string | null;
  reporting_period: string | null;
  extraction_method: string | null;
}

export interface DimensionBasis {
  finding_id?: number;
  title?: string;
  points?: number;
  verification?: string;
  note?: string;
}

export interface Dimension {
  label: string;
  weight: number;
  risk_score: number | null;
  risk_level: string;
  coverage: number;
  reliability: string;
  confidence: number | null;
  findings: number;
  basis: DimensionBasis[];
}

export interface Overall {
  risk_score: number | null;
  risk_level: string;
  coverage: number;
  reliability: string;
  confidence: number | null;
}

export interface FindingEntry {
  id: number;
  title: string;
  agent: string;
  category: string;
  status: string;
  severity: string;
  verification_status: string;
  confidence: number | null;
  claim_id: number | null;
  recommended_followup: string | null;
  evidence_ids: number[];
}

export interface ReportContent {
  title: string;
  executive_summary: string;
  executive_summary_source: string;
  overall: Overall;
  dimensions: Record<string, Dimension>;
  supported_findings: FindingEntry[];
  issues_for_review: FindingEntry[];
  unresolved_questions: FindingEntry[];
  recommended_followups: string[];
  finding_counts: Record<string, number>;
  verification_counts: Record<string, number>;
  limitations: string[];
  disclaimers: string[];
}

export interface Report {
  id: number;
  application_id: number;
  summary: string | null;
  content: ReportContent;
  review_status: string;
  created_at: string;
}

export interface DemoCase {
  slug: string;
  company: string;
  sector: string | null;
  location: string | null;
  project: string;
  requested_amount_pkr: number;
  documents: string[];
}

export function parseDate(value: string | null): Date | null {
  if (!value) return null;
  return new Date(/(Z|[+-]\d{2}:?\d{2})$/.test(value) ? value : `${value}Z`);
}

export function formatDate(value: string | null): string {
  const d = parseDate(value);
  return d ? d.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }) : "-";
}

export function money(amount: number | null, currency: string): string {
  return amount == null ? "-" : `${currency} ${amount.toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
}

export function duration(start: string | null, end: string | null): string {
  const a = parseDate(start);
  const b = parseDate(end);
  if (!a || !b) return "";
  const s = Math.max(0, (b.getTime() - a.getTime()) / 1000);
  return s < 60 ? `${s.toFixed(1)}s` : `${Math.floor(s / 60)}m ${Math.round(s % 60)}s`;
}