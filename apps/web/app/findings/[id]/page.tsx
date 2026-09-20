"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { ErrorState } from "@/components/ui/error-state";
import { PageSkeleton } from "@/components/ui/skeleton";
import {
  fetchBriefing,
  fetchPrecedents,
  resolveDecision,
  searchEvidence,
  type Briefing,
  type EvidenceSearch,
  type PrecedentRow,
} from "@/lib/api";
import {
  decisionStatusLabel,
  findingStatusLabel,
  formatDate,
  humanize,
  invoiceStatusLabel,
  precedentStatusLabel,
  riskVariant,
  statusTone,
} from "@/lib/display";
import { buildFindingMemo } from "@/lib/finding-context";
import { cn } from "@/lib/utils";

export default function FindingDetailPage() {
  const params = useParams<{ id: string }>();
  const [briefing, setBriefing] = useState<Briefing | null>(null);
  const [precedents, setPrecedents] = useState<PrecedentRow[]>([]);
  const [search, setSearch] = useState<EvidenceSearch | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);

  async function reload() {
    const [next, rows] = await Promise.all([fetchBriefing(), fetchPrecedents()]);
    if (!next) {
      console.error("Briefing unavailable for finding memo");
      setError("This finding is unavailable. Start the API on :8000.");
    } else {
      setError(null);
      setBriefing(next);
    }
    setPrecedents(rows);
  }

  useEffect(() => {
    reload().catch((err) => {
      console.error("Failed to open finding memo", err);
      setError("This finding is unavailable.");
    });
  }, []);

  const finding = briefing?.findings.find((row) => row.id === params.id) ?? null;
  const memo = useMemo(
    () => (finding && briefing ? buildFindingMemo(finding, briefing, precedents) : null),
    [finding, briefing, precedents],
  );

  useEffect(() => {
    if (!memo?.query || memo.query.length < 2) {
      setSearch(null);
      return;
    }
    const handle = window.setTimeout(() => {
      searchEvidence(memo.query)
        .then(setSearch)
        .catch((err) => {
          console.error("Evidence search failed for finding memo", err);
          setSearch(null);
        });
    }, 150);
    return () => window.clearTimeout(handle);
  }, [memo?.query]);

  async function onResolve(resolution: "approve" | "reject") {
    if (!memo?.primaryDecision) return;
    setBusy(true);
    setNote(null);
    const result = await resolveDecision(memo.primaryDecision.id, resolution);
    await reload();
    setNote(
      result
        ? resolution === "approve"
          ? "Approved. The queue is updated."
          : "Rejected. The queue is updated."
        : "The decision did not save. Check that the API is running.",
    );
    setBusy(false);
  }

  if (error) {
    return <ErrorState title="Finding unavailable">{error}</ErrorState>;
  }

  if (!briefing) {
    return <PageSkeleton label="Opening the memo" variant="memo" />;
  }

  if (!finding || !memo) {
    return (
      <div className="mx-auto max-w-3xl space-y-4">
        <BackLink />
        <p className="text-sm leading-6 text-mute">This finding is not in the current briefing.</p>
      </div>
    );
  }

  const evidenceHits = search?.hits.slice(0, 5) ?? [];
  const hasEvidence = memo.documents.length > 0 || evidenceHits.length > 0;
  const findingStatus = findingStatusLabel(finding.status);
  const activity = [
    ...memo.invoices
      .filter((invoice) => invoice.due_date)
      .map((invoice) => {
        const due = formatDate(invoice.due_date);
        return due ? `Invoice ${invoice.invoice_number} due ${due}` : null;
      }),
    ...memo.invoices
      .filter((invoice) => invoice.status)
      .map((invoice) => `${invoice.invoice_number} is ${invoiceStatusLabel(invoice.status)}`),
    ...memo.documents
      .filter((doc) => doc.ingested_at)
      .map((doc) => {
        const received = formatDate(doc.ingested_at);
        return received ? `Source received ${received} · ${doc.filename}` : `Source · ${doc.filename}`;
      }),
    ...memo.decisions.map((decision) =>
      decisionStatusLabel(decision.status, decision.requires_human_approval),
    ),
  ].filter((item): item is string => Boolean(item));

  return (
    <div className="mx-auto max-w-3xl space-y-8">
      <BackLink />

      <header className="space-y-4">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant={riskVariant(finding.severity)}>{humanize(finding.severity)}</Badge>
          <Badge variant={statusTone(findingStatus)}>{findingStatus}</Badge>
          {memo.approval ? <Badge variant={statusTone(memo.approval)}>{memo.approval}</Badge> : null}
        </div>
        <h2 className="font-serif text-3xl leading-snug tracking-tight text-ivory">{finding.title}</h2>
        {memo.impact ? (
          <p className="font-serif text-4xl tabular-nums tracking-tight text-ivory">{memo.impact}</p>
        ) : null}
        {memo.summary ? <p className="max-w-2xl text-sm leading-6 text-mute">{memo.summary}</p> : null}
      </header>

      {memo.recommendation ? (
        <MemoSection title="Mira recommends">
          <p className="text-base leading-7 text-ivory">{memo.recommendation}</p>
        </MemoSection>
      ) : null}

      {memo.why ? (
        <MemoSection title="Why this was flagged">
          <p className="text-sm leading-7 text-mute">{memo.why}</p>
        </MemoSection>
      ) : null}

      {hasEvidence ? (
        <MemoSection title="Evidence">
          <ul className="space-y-3">
            {memo.documents.map((doc) => (
              <li key={doc.id} className="text-sm leading-6">
                <p className="text-ivory">{doc.filename}</p>
                <p className="text-mute">
                  {humanize(doc.document_class)}
                  {doc.lineage ? ` · ${doc.lineage}` : null}
                </p>
              </li>
            ))}
            {evidenceHits.map((hit) => (
              <li key={`${hit.object_type}-${hit.object_id}-${hit.title}`} className="text-sm leading-6">
                <p className="text-ivory">{hit.title}</p>
                <p className="text-mute">
                  {humanize(hit.object_type)}
                  {hit.snippet ? ` · ${hit.snippet}` : null}
                </p>
              </li>
            ))}
          </ul>
        </MemoSection>
      ) : null}

      {memo.primaryDecision?.policy_basis ? (
        <MemoSection title="Relevant policy">
          <p className="text-sm leading-7 text-mute">{memo.primaryDecision.policy_basis}</p>
        </MemoSection>
      ) : null}

      {memo.primaryDecision?.authority_basis ? (
        <MemoSection title="Who must approve">
          <p className="text-sm leading-7 text-mute">{memo.primaryDecision.authority_basis}</p>
        </MemoSection>
      ) : null}

      {memo.precedents.length > 0 ? (
        <MemoSection title="Relevant precedent">
          <ul className="space-y-3">
            {memo.precedents.map((row) => (
              <li key={row.id} className="text-sm leading-6">
                <p className="text-ivory">{row.summary}</p>
                <p className="text-mute">
                  {precedentStatusLabel(row.status)}
                  {row.period ? ` · ${row.period}` : null}
                </p>
              </li>
            ))}
          </ul>
        </MemoSection>
      ) : null}

      {activity.length > 0 ? (
        <MemoSection title="Related activity">
          <ul className="space-y-2 text-sm leading-6 text-mute">
            {activity.slice(0, 6).map((item, index) => (
              <li key={`${index}-${item}`}>{item}</li>
            ))}
          </ul>
        </MemoSection>
      ) : null}

      <section className="border-t border-line pt-6">
        <p className="text-xs tracking-wide text-mute">Next step</p>
        {note ? (
          <p className={cn("mt-2 text-sm leading-6", note.includes("did not save") ? "text-alert" : "text-ledger")}>
            {note}
          </p>
        ) : null}
        <div className="mt-4 flex flex-wrap items-center gap-2">
          {memo.canApprove && memo.primaryDecision ? (
            <>
              <Button type="button" disabled={busy} onClick={() => onResolve("approve")}>
                {busy ? "Saving…" : "Approve"}
              </Button>
              <Button type="button" variant="outline" disabled={busy} onClick={() => onResolve("reject")}>
                Reject
              </Button>
            </>
          ) : null}
          <Link
            href={memo.query ? `/evidence?q=${encodeURIComponent(memo.query)}` : "/evidence"}
            className={buttonVariants({ variant: "outline" })}
          >
            Open evidence
          </Link>
          {memo.primaryDecision ? (
            <Link
              href="/decisions"
              className="inline-flex h-10 items-center rounded-md px-3 text-sm text-mute transition-colors hover:text-ivory focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brass/60"
            >
              View approvals
            </Link>
          ) : null}
        </div>
      </section>
    </div>
  );
}

function BackLink() {
  return (
    <Link
      href="/findings"
      className="inline-flex text-sm text-mute transition-colors hover:text-ivory focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brass/60"
    >
      ← Findings
    </Link>
  );
}

function MemoSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-3">
      <h3 className="text-xs tracking-wide text-mute">{title}</h3>
      {children}
    </section>
  );
}
