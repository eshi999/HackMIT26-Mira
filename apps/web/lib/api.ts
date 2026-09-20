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
  content_hash?: string | null;
  extraction_status?: string | null;
  ingested_at?: string | null;
  lineage?: string | null;
  evidence_title?: string | null;
};

export type EvidenceHit = {
  object_type: string;
  object_id: string | null;
  title: string;
  snippet: string | null;
  source_system: string;
};

export type EvidenceSearch = {
  query: string;
  retrieval_source: string;
  hit_count: number;
  explanation: string;
  hits: EvidenceHit[];
};

export type PrecedentRow = {
  id: string;
  summary: string;
  outcome: string;
  scope: string;
  status: string;
  authorizer: string | null;
  reusable_rule: string | null;
  conditions: Record<string, unknown> | null;
  period: string;
};

export type ExecutiveResult = {
  run_id: string;
  request: string;
  kind: string;
  recommendation: { headline: string; body: string };
  artifact: Record<string, unknown>;
  transcript?: string;
  voice_output_available?: boolean;
};

export type MeasuredContext = {
  tokens_avoided: number;
  reduction_percent: string;
  correctness_retained: boolean;
  scenario_count: number;
  correctness_retained_label: string;
  baseline: { estimated_input_tokens: number };
  optimized: { estimated_input_tokens: number };
  source?: string;
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
const TOKEN = process.env.NEXT_PUBLIC_MIRA_DEMO_TOKEN ?? "mira-demo-elena";

function authHeaders(json = false): HeadersInit {
  return {
    Authorization: `Bearer ${TOKEN}`,
    ...(json ? { "Content-Type": "application/json" } : {}),
  };
}

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
  try {
    const res = await fetch(`${API}/api/v1/decisions/${decisionId}/resolve`, {
      method: "POST",
      cache: "no-store",
      headers: authHeaders(true),
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

export async function postExecutiveRequest(request: string): Promise<ExecutiveResult | null> {
  try {
    const res = await fetch(`${API}/api/v1/executive/request`, {
      method: "POST",
      cache: "no-store",
      headers: authHeaders(true),
      body: JSON.stringify({ request }),
    });
    if (!res.ok) return null;
    return (await res.json()) as ExecutiveResult;
  } catch {
    return null;
  }
}

export async function fetchVoiceStatus(): Promise<{ stt: string; tts: string } | null> {
  try {
    const res = await fetch(`${API}/api/v1/voice/status`, { cache: "no-store" });
    if (!res.ok) return null;
    return (await res.json()) as { stt: string; tts: string };
  } catch {
    return null;
  }
}

export async function postVoiceRequest(audio: Blob): Promise<ExecutiveResult | { error: string }> {
  const body = new FormData();
  body.append("audio", audio, "clip.webm");
  try {
    const res = await fetch(`${API}/api/v1/voice/request`, {
      method: "POST",
      cache: "no-store",
      headers: { Authorization: `Bearer ${TOKEN}` },
      body,
    });
    if (res.status === 503) {
      const payload = (await res.json()) as { detail?: string };
      return { error: payload.detail ?? "Deepgram is unavailable. Type the request instead." };
    }
    if (!res.ok) return { error: "Voice request failed. Type the request instead." };
    return (await res.json()) as ExecutiveResult;
  } catch {
    return { error: "Voice request failed. Type the request instead." };
  }
}

export async function speakMiraResult(text: string): Promise<Blob | null> {
  try {
    const res = await fetch(`${API}/api/v1/voice/speak`, {
      method: "POST",
      cache: "no-store",
      headers: authHeaders(true),
      body: JSON.stringify({ text, source: "mira_result" }),
    });
    if (!res.ok) return null;
    return await res.blob();
  } catch {
    return null;
  }
}

export async function searchEvidence(query: string): Promise<EvidenceSearch | null> {
  try {
    const res = await fetch(`${API}/api/v1/evidence/search?q=${encodeURIComponent(query)}`, {
      cache: "no-store",
    });
    if (!res.ok) return null;
    return (await res.json()) as EvidenceSearch;
  } catch {
    return null;
  }
}

export async function fetchPrecedents(): Promise<PrecedentRow[]> {
  try {
    const res = await fetch(`${API}/api/v1/precedents`, { cache: "no-store" });
    if (!res.ok) return [];
    const body = (await res.json()) as { precedents: PrecedentRow[] };
    return body.precedents ?? [];
  } catch {
    return [];
  }
}

export async function authorizePrecedent(payload: {
  summary: string;
  reusable_rule: string;
  outcome: string;
  scope: string;
  vendor: string;
  category: string;
  amount_threshold: string;
  effective_date: string;
  evidence: string[];
}): Promise<Record<string, unknown> | null> {
  try {
    const res = await fetch(`${API}/api/v1/precedents/authorize`, {
      method: "POST",
      cache: "no-store",
      headers: authHeaders(true),
      body: JSON.stringify(payload),
    });
    if (!res.ok) return null;
    return (await res.json()) as Record<string, unknown>;
  } catch {
    return null;
  }
}

export async function fetchMeasuredContext(): Promise<MeasuredContext | null> {
  try {
    const res = await fetch(`${API}/api/v1/context/measured`, {
      cache: "no-store",
      headers: authHeaders(),
    });
    if (!res.ok) return null;
    return (await res.json()) as MeasuredContext;
  } catch {
    return null;
  }
}

export async function fetchSpaceSignals(): Promise<Record<string, unknown> | null> {
  try {
    const res = await fetch(`${API}/api/v1/external-signals/space`, { cache: "no-store" });
    if (!res.ok) return null;
    return (await res.json()) as Record<string, unknown>;
  } catch {
    return null;
  }
}
