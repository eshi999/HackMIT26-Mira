import { usd } from "@/lib/utils";

export function humanize(value: string) {
  const text = value.replaceAll("_", " ").trim();
  return text ? text.charAt(0).toUpperCase() + text.slice(1) : text;
}

export function firstSentence(text: string, max = 180) {
  const trimmed = text.replace(/\s+/g, " ").trim();
  if (!trimmed) return "";
  const match = trimmed.match(/^.+?[.!?](?=\s|$)/);
  const sentence = match ? match[0] : trimmed;
  if (sentence.length <= max) return sentence;
  return `${sentence.slice(0, max - 1).trimEnd()}…`;
}

export function remainderAfterFirstSentence(text: string) {
  const trimmed = text.replace(/\s+/g, " ").trim();
  const first = firstSentence(trimmed, 1000);
  const rest = trimmed.slice(first.length).trim();
  return rest;
}

export function money(value: number | string | null | undefined) {
  if (value === null || value === undefined || value === "") return null;
  const n = Number(value);
  if (!Number.isFinite(n) || n === 0) return null;
  return usd(n);
}

export function formatHours(value: number | string | null | undefined) {
  if (value === null || value === undefined || value === "") return null;
  const n = Number(value);
  if (!Number.isFinite(n)) return null;
  return `${n.toFixed(1)}h`;
}

export function formatPercent(value: number | string | null | undefined) {
  if (value === null || value === undefined || value === "") return null;
  const n = Number(value);
  if (!Number.isFinite(n)) return null;
  const pct = n >= 0 && n <= 1 ? n * 100 : n;
  return `${pct.toFixed(0)}%`;
}

export function formatDate(value: string | null | undefined) {
  if (!value) return null;
  const dateOnly = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value.trim());
  if (dateOnly) {
    const date = new Date(Number(dateOnly[1]), Number(dateOnly[2]) - 1, Number(dateOnly[3]));
    return date.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export function formatDateTime(value: string | null | undefined) {
  if (!value) return null;
  if (/^\d{4}-\d{2}-\d{2}$/.test(value.trim())) return formatDate(value);
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export function formatCoord(value: number | string | null | undefined) {
  if (value === null || value === undefined || value === "") return null;
  const n = Number(value);
  if (!Number.isFinite(n)) return null;
  return n.toFixed(2);
}

export function riskVariant(level: string): "alert" | "default" | "mute" {
  if (level === "critical" || level === "high") return "alert";
  if (level === "medium") return "default";
  return "mute";
}

export type StatusTone = "alert" | "ledger" | "mute" | "default";

export function statusTone(label: string): StatusTone {
  const key = label.toLowerCase();
  if (
    key === "needs review" ||
    key === "needs approval" ||
    key === "rejected" ||
    key === "failed" ||
    key === "critical" ||
    key === "high"
  ) {
    return "alert";
  }
  if (
    key === "approved" ||
    key === "resolved" ||
    key === "monitoring" ||
    key === "live" ||
    key === "active" ||
    key === "paid" ||
    key === "voice ready"
  ) {
    return "ledger";
  }
  return "mute";
}

const DECISION_STATUS_LABELS: Record<string, string> = {
  awaiting_human: "Needs approval",
  awaiting_approval: "Needs approval",
  pending: "Needs review",
  pending_review: "Needs review",
  review_required: "Needs review",
  needs_review: "Needs review",
  proposed: "Needs review",
  evaluated: "Needs review",
  approved: "Approved",
  rejected: "Rejected",
  executed: "Resolved",
  completed: "Resolved",
  failed: "Failed",
  superseded: "Superseded",
};

export function decisionStatusLabel(status: string, requiresHuman = false) {
  const key = status.toLowerCase();
  if (requiresHuman && (key === "proposed" || key === "evaluated" || key === "pending" || key === "pending_review")) {
    return "Needs approval";
  }
  return DECISION_STATUS_LABELS[key] ?? humanize(status);
}

const FINDING_STATUS_LABELS: Record<string, string> = {
  open: "Needs review",
  pending_review: "Needs review",
  review_required: "Needs review",
  acknowledged: "Monitoring",
  monitoring: "Monitoring",
  resolved: "Resolved",
  closed: "Resolved",
  dismissed: "Resolved",
};

export function findingStatusLabel(status: string) {
  return FINDING_STATUS_LABELS[status.toLowerCase()] ?? humanize(status);
}

const INVOICE_STATUS_LABELS: Record<string, string> = {
  needs_review: "Needs review",
  pending_review: "Needs review",
  review_required: "Needs review",
  awaiting_approval: "Needs approval",
  awaiting_human: "Needs approval",
  approved: "Approved",
  rejected: "Rejected",
  paid: "Paid",
};

export function invoiceStatusLabel(status: string) {
  return INVOICE_STATUS_LABELS[status.toLowerCase()] ?? humanize(status);
}

const PRECEDENT_STATUS_LABELS: Record<string, string> = {
  active: "Active",
  revoked: "Revoked",
  rejected: "Rejected",
};

export function precedentStatusLabel(status: string) {
  return PRECEDENT_STATUS_LABELS[status.toLowerCase()] ?? humanize(status);
}

export function decisionTitle(action: string, decisionType?: string | null) {
  const title = humanize(action);
  const generic = new Set(["hold", "reject", "pay", "approve"]);
  if (generic.has(action.toLowerCase()) && decisionType) {
    return `${humanize(decisionType)} · ${title}`;
  }
  return title;
}

export const SEVERITY_RANK: Record<string, number> = {
  critical: 0,
  high: 1,
  medium: 2,
  low: 3,
};
