export type Company = {
  id: string;
  slug: string;
  name: string;
  legal_name: string;
  industry: string;
  stage: string;
  employee_count: number | null;
  description: string | null;
};

export type DecisionBrief = {
  id: string;
  decision_type: string;
  status: string;
  action: string;
  rationale: string;
  confidence_score: number | string;
  risk_level: string;
  policy_basis: string;
  authority_basis: string;
  requires_human_approval: boolean;
  dollars_impact: number | string | null;
  hours_saved_estimate: number | string | null;
  subject_type: string | null;
};

export type FindingBrief = {
  id: string;
  finding_type: string;
  severity: string;
  title: string;
  description: string;
  status: string;
};

export type InvoiceBrief = {
  id: string;
  invoice_number: string;
  vendor_name: string | null;
  total: number | string;
  currency: string;
  status: string;
  due_date: string | null;
  is_duplicate_suspect: boolean;
};

export type SignalOut = {
  series_id: string;
  title: string;
  value: number | string;
  unit: string;
  as_of: string;
  source: string;
  note: string | null;
};

export type DocumentBrief = {
  id: string;
  filename: string;
  document_class: string;
  storage_backend: string;
  storage_uri: string;
};

export type Briefing = {
  company: Company;
  mira_status: string;
  headline: string;
  narrative: string;
  cash: { amount: number | string; currency: string; account_name: string };
  open_ap: number | string;
  savings: {
    dollars_protected: number | string;
    dollars_saved?: number | string;
    hours_saved: number | string;
    period: string;
    source?: string;
  };
  pending_decisions: DecisionBrief[];
  findings: FindingBrief[];
  invoices: InvoiceBrief[];
  signals: SignalOut[];
  documents_ingested: number;
  inbox: DocumentBrief[];
  sandbox_notice: string;
  autonomous_completion_rate?: number | string;
  reconciliation_rate?: number | string;
  open_incidents?: number;
  blocked_payments?: number;
  pending_approvals?: number;
  close?: {
    period: string;
    completion_pct: number | string;
    completed: string[];
    blocked: string[];
    audit_status: string;
  } | null;
};

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function fetchBriefing(): Promise<Briefing | null> {
  try {
    const res = await fetch(`${API}/api/v1/briefing`, { cache: "no-store" });
    if (!res.ok) return null;
    return (await res.json()) as Briefing;
  } catch {
    return null;
  }
}

export async function resolveDecision(
  decisionId: string,
  resolution: "approve" | "reject",
  comment?: string,
): Promise<Record<string, unknown> | null> {
  const token = process.env.NEXT_PUBLIC_MIRA_DEMO_TOKEN ?? "mira-demo-elena";
  try {
    const res = await fetch(`${API}/api/v1/decisions/${decisionId}/resolve`, {
      method: "POST",
      cache: "no-store",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ resolution, comment: comment ?? null }),
    });
    if (!res.ok) return null;
    return (await res.json()) as Record<string, unknown>;
  } catch {
    return null;
  }
}

export async function fetchMeta(): Promise<Record<string, unknown> | null> {
  try {
    const res = await fetch(`${API}/api/v1/meta`, { cache: "no-store" });
    if (!res.ok) return null;
    return (await res.json()) as Record<string, unknown>;
  } catch {
    return null;
  }
}
