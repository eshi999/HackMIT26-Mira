import type {
  Briefing,
  DecisionBrief,
  DocumentBrief,
  FindingBrief,
  InvoiceBrief,
  PrecedentRow,
} from "@/lib/api";
import {
  decisionStatusLabel,
  firstSentence,
  money,
  remainderAfterFirstSentence,
  SEVERITY_RANK,
} from "@/lib/display";

const GENERIC_TOKENS = new Set([
  "invoice",
  "amount",
  "vendor",
  "payment",
  "overdue",
  "missing",
  "purchase",
  "order",
  "document",
  "duplicate",
  "unusual",
  "flagged",
  "this",
  "that",
  "from",
  "with",
  "within",
]);

function escapeRegExp(value: string) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function haystack(finding: FindingBrief) {
  return `${finding.title} ${finding.description}`;
}

function hasToken(text: string, token: string) {
  if (!token || token.length < 3) return false;
  const re = new RegExp(`(^|[^a-z0-9])${escapeRegExp(token)}([^a-z0-9]|$)`, "i");
  return re.test(text);
}

function tokens(text: string) {
  return (text.toLowerCase().match(/[a-z][a-z0-9-]{3,}/g) ?? []).filter(
    (token) => !GENERIC_TOKENS.has(token),
  );
}

function overlap(a: string, b: string) {
  const left = new Set(tokens(a));
  return tokens(b).some((token) => left.has(token));
}

function extractAmounts(text: string) {
  const found = new Set<number>();
  for (const match of text.matchAll(/\$([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2})?)/g)) {
    found.add(Number(match[1].replaceAll(",", "")));
  }
  for (const match of text.matchAll(/\b([0-9]{3,}(?:\.[0-9]{2}))\b/g)) {
    found.add(Number(match[1]));
  }
  return [...found].filter((value) => value >= 100);
}

export function relatedInvoices(finding: FindingBrief, invoices: InvoiceBrief[]) {
  const text = haystack(finding);
  return invoices.filter((invoice) => {
    if (hasToken(text, invoice.invoice_number)) return true;
    const vendor = invoice.vendor_name?.trim();
    if (vendor && vendor.length >= 5 && text.toLowerCase().includes(vendor.toLowerCase())) {
      return true;
    }
    return false;
  });
}

export function relatedDecisions(finding: FindingBrief, briefing: Briefing, invoices: InvoiceBrief[]) {
  const text = haystack(finding);
  const amounts = new Set(extractAmounts(text));
  const invoiceNumbers = invoices.map((invoice) => invoice.invoice_number);
  const amountCounts = new Map<number, number>();
  for (const decision of briefing.pending_decisions) {
    const value = Number(decision.dollars_impact);
    if (!Number.isNaN(value) && value > 0) {
      amountCounts.set(value, (amountCounts.get(value) ?? 0) + 1);
    }
  }

  return briefing.pending_decisions.filter((decision) => {
    const blob = `${decision.action} ${decision.rationale} ${decision.policy_basis}`;
    if (invoiceNumbers.some((number) => hasToken(blob, number))) return true;
    const value = Number(decision.dollars_impact);
    const amountHit = !Number.isNaN(value) && amounts.has(value);
    if (
      amountHit &&
      finding.finding_type.includes("duplicate") &&
      decision.action.toLowerCase().includes("duplicate")
    ) {
      return true;
    }
    if (amountHit && (amountCounts.get(value) ?? 0) === 1) return true;
    if (amountHit && overlap(text, blob)) return true;
    return false;
  });
}

export function relatedDocuments(finding: FindingBrief, documents: DocumentBrief[], invoices: InvoiceBrief[]) {
  const text = haystack(finding).toLowerCase();
  const numbers = invoices.map((invoice) => invoice.invoice_number.toLowerCase());
  const titleTokens = tokens(finding.title).filter((token) => token.length >= 5);
  return documents.filter((doc) => {
    const filename = doc.filename.toLowerCase();
    const lineage = (doc.lineage ?? "").toLowerCase();
    const blob = `${filename} ${lineage}`;
    if (numbers.some((number) => blob.includes(number))) return true;
    if (titleTokens.some((token) => blob.includes(token))) return true;
    if (doc.evidence_title && text.includes(doc.evidence_title.toLowerCase())) return true;
    return false;
  });
}

export function relatedPrecedents(finding: FindingBrief, precedents: PrecedentRow[]) {
  const text = haystack(finding);
  return precedents.filter((row) => {
    const blob = `${row.summary} ${row.scope} ${row.reusable_rule ?? ""}`;
    return overlap(text, blob);
  });
}

export function evidenceQuery(finding: FindingBrief, invoices: InvoiceBrief[]) {
  if (invoices[0]?.invoice_number) return invoices[0].invoice_number;
  const vendor = invoices.find((invoice) => invoice.vendor_name)?.vendor_name;
  if (vendor && vendor.length >= 4) return vendor;
  const distinctive = tokens(finding.title).find((token) => token.length >= 6);
  return distinctive ?? "";
}

export function recommendationFor(decision: DecisionBrief) {
  const action = decision.action.toLowerCase();
  if (action.includes("dual_approval")) {
    return "Mira recommends dual approval before this purchase proceeds.";
  }
  if (action.includes("reject_duplicate")) {
    return "Mira recommends blocking this as a duplicate.";
  }
  if (action.includes("reject")) {
    return "Mira recommends rejecting this item.";
  }
  if (action.includes("hold")) {
    return "Mira recommends holding this item until you review it.";
  }
  if (action.includes("pay")) {
    return "Mira recommends paying only after you approve.";
  }
  if (decision.requires_human_approval) {
    return "Needs your approval before anything further happens.";
  }
  return null;
}

export function approvalLabel(decision: DecisionBrief | null) {
  if (!decision) return null;
  return decisionStatusLabel(decision.status, decision.requires_human_approval);
}

function pickPrimaryDecision(decisions: DecisionBrief[]) {
  const waiting = decisions.filter(
    (decision) => decision.requires_human_approval && decision.status === "awaiting_human",
  );
  if (waiting.length) {
    return [...waiting].sort(
      (a, b) => Number(b.dollars_impact ?? 0) - Number(a.dollars_impact ?? 0),
    )[0];
  }
  if (!decisions.length) return null;
  return [...decisions].sort(
    (a, b) => Number(b.dollars_impact ?? 0) - Number(a.dollars_impact ?? 0),
  )[0];
}

export type FindingMemo = {
  finding: FindingBrief;
  summary: string;
  why: string;
  invoices: InvoiceBrief[];
  documents: DocumentBrief[];
  decisions: DecisionBrief[];
  precedents: PrecedentRow[];
  primaryDecision: DecisionBrief | null;
  recommendation: string | null;
  approval: string | null;
  impact: string | null;
  query: string;
  canApprove: boolean;
};

export function buildFindingMemo(
  finding: FindingBrief,
  briefing: Briefing,
  precedents: PrecedentRow[],
): FindingMemo {
  const invoices = relatedInvoices(finding, briefing.invoices);
  const documents = relatedDocuments(finding, briefing.inbox, invoices);
  const decisions = relatedDecisions(finding, briefing, invoices);
  const relatedPrecedent = relatedPrecedents(finding, precedents);
  const primaryDecision = pickPrimaryDecision(decisions);
  const impact =
    money(primaryDecision?.dollars_impact) ??
    (invoices.length === 1 ? money(invoices[0].total) : null);
  const summary = firstSentence(finding.description) || firstSentence(finding.title);
  const why = remainderAfterFirstSentence(finding.description);

  return {
    finding,
    summary,
    why,
    invoices,
    documents,
    decisions,
    precedents: relatedPrecedent,
    primaryDecision,
    recommendation: primaryDecision ? recommendationFor(primaryDecision) : null,
    approval: approvalLabel(primaryDecision),
    impact,
    query: evidenceQuery(finding, invoices),
    canApprove: Boolean(
      primaryDecision &&
        primaryDecision.requires_human_approval &&
        primaryDecision.status === "awaiting_human",
    ),
  };
}

export function sortFindings(findings: FindingBrief[]) {
  return [...findings].sort((a, b) => {
    const severity =
      (SEVERITY_RANK[a.severity] ?? 9) - (SEVERITY_RANK[b.severity] ?? 9);
    if (severity !== 0) return severity;
    if (a.status !== b.status) return a.status === "open" ? -1 : 1;
    return a.title.localeCompare(b.title);
  });
}
