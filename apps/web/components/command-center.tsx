"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { MiraRequest } from "@/components/mira-request";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { ListPanel, listRowClassName, listRowInteractiveClassName } from "@/components/ui/list-panel";
import { PageSkeleton } from "@/components/ui/skeleton";
import { SectionHeading } from "@/components/ui/section-heading";
import { Stat } from "@/components/ui/stat";
import { fetchBriefing, type Briefing, type DecisionBrief, type FindingBrief } from "@/lib/api";
import {
  decisionStatusLabel,
  decisionTitle,
  firstSentence,
  findingStatusLabel,
  formatHours,
  formatPercent,
  humanize,
  money,
  riskVariant,
  SEVERITY_RANK,
  statusTone,
} from "@/lib/display";
import { buildFindingMemo, recommendationFor } from "@/lib/finding-context";
import { cn } from "@/lib/utils";

const ATTENTION_LIMIT = 4;
const FINDING_LIMIT = 4;
const RESOLVED_LIMIT = 5;
const RESOLVED_DECISION = new Set(["executed", "approved", "rejected"]);

function attentionItems(briefing: Briefing) {
  return briefing.pending_decisions
    .filter((d) => d.requires_human_approval && d.status === "awaiting_human")
    .sort((a, b) => {
      const risk = (SEVERITY_RANK[a.risk_level] ?? 9) - (SEVERITY_RANK[b.risk_level] ?? 9);
      if (risk !== 0) return risk;
      return Number(b.dollars_impact ?? 0) - Number(a.dollars_impact ?? 0);
    });
}

function recentFindings(briefing: Briefing) {
  return [...briefing.findings].sort((a, b) => {
    const severity = (SEVERITY_RANK[a.severity] ?? 9) - (SEVERITY_RANK[b.severity] ?? 9);
    if (severity !== 0) return severity;
    if (a.status !== b.status) return a.status === "open" ? -1 : 1;
    return a.title.localeCompare(b.title);
  });
}

function resolvedDecisions(briefing: Briefing) {
  return briefing.pending_decisions.filter((d) => RESOLVED_DECISION.has(d.status));
}

export function CommandCenter() {
  const [briefing, setBriefing] = useState<Briefing | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchBriefing()
      .then((data) => {
        if (!data) {
          console.error("Briefing unavailable for command center");
          setError("Mira's office is not reachable. Start the API on :8000.");
        } else setBriefing(data);
      })
      .catch((err) => {
        console.error("Failed to load command center", err);
        setError("Mira's office is not reachable.");
      });
  }, []);

  if (error) {
    return <ErrorState title="Mira is offline">{error} The command center does not fall back to a chatbot.</ErrorState>;
  }

  if (!briefing) {
    return <PageSkeleton label="Opening the office" variant="dashboard" />;
  }

  const needsYou = attentionItems(briefing);
  const findings = recentFindings(briefing);
  const resolved = resolvedDecisions(briefing);
  const approvalCount = briefing.pending_approvals ?? needsYou.length;
  const protectedDollars = money(briefing.savings.dollars_protected);
  const cash = money(briefing.cash.amount);
  const openAp = money(briefing.open_ap);
  const saved = money(briefing.savings.dollars_saved);
  const hoursReturned = formatHours(briefing.savings.hours_saved);
  const closePct = briefing.close ? formatPercent(briefing.close.completion_pct) : null;
  const showSaved = saved !== null;

  return (
    <div className="space-y-8">
      <section className="max-w-3xl">
        <p className="text-xs text-mute">Overnight review</p>
        <h2 className="mt-3 font-serif text-3xl leading-snug tracking-tight text-ivory">
          {briefing.headline}
        </h2>
        <p className="mt-3 text-sm leading-6 text-mute">{briefing.narrative}</p>
        {briefing.close ? (
          <p className="mt-3 text-sm leading-6 text-mute">
            Period {briefing.close.period} close
            {closePct ? ` is ${closePct} complete` : ""}
            {briefing.close.blocked.length ? ` · ${briefing.close.blocked.length} items blocked` : null}
            {briefing.close.completed.length ? ` · ${briefing.close.completed.length} complete` : null}.
          </p>
        ) : null}
      </section>

      <section
        aria-label="Key figures"
        className="grid grid-cols-2 overflow-hidden rounded-lg border border-line lg:grid-cols-4"
      >
        <div className="border-b border-r border-line p-5 lg:border-b-0">
          <Stat
            label="Protected"
            value={protectedDollars ?? "—"}
            valueClassName="text-ledger"
            hint={briefing.savings.period ? `Overnight · ${briefing.savings.period}` : "Overnight"}
          />
        </div>
        <div className="border-b border-line p-5 lg:border-b-0 lg:border-r">
          <Stat
            label="Hours returned"
            value={hoursReturned ?? "—"}
            hint="Time returned to the team"
          />
        </div>
        <div className="border-r border-line p-5">
          <Stat
            label="Operating cash"
            value={cash ?? "—"}
            hint={
              openAp
                ? `${briefing.cash.account_name} · Open AP ${openAp}`
                : briefing.cash.account_name
            }
          />
        </div>
        <Link
          href="/decisions"
          className="p-5 transition-colors hover:bg-white/[0.02] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brass/60 focus-visible:ring-inset"
        >
          <Stat
            label="Needs approval"
            value={approvalCount}
            hint="Awaiting a human"
            valueClassName={Number(approvalCount) > 0 ? "text-alert" : "text-ivory"}
          />
        </Link>
      </section>

      {showSaved ? <p className="text-sm leading-6 text-mute">Dollars saved this period: {saved}.</p> : null}

      <MiraRequest />

      <section className="space-y-3">
        <SectionHeading
          title="Needs approval"
          meta={needsYou.length ? `${Math.min(ATTENTION_LIMIT, needsYou.length)} of ${needsYou.length}` : undefined}
          href={needsYou.length ? "/decisions" : undefined}
          linkLabel={needsYou.length ? `Review all ${needsYou.length}` : undefined}
        />
        {needsYou.length === 0 ? (
          <EmptyState>No items need approval.</EmptyState>
        ) : (
          <ListPanel>
            {needsYou.slice(0, ATTENTION_LIMIT).map((decision) => (
              <AttentionRow key={decision.id} decision={decision} />
            ))}
          </ListPanel>
        )}
      </section>

      <section className="space-y-3">
        <SectionHeading
          title="Findings"
          meta={findings.length ? `${Math.min(FINDING_LIMIT, findings.length)} of ${findings.length}` : undefined}
          href={findings.length ? "/findings" : undefined}
          linkLabel="Open findings"
        />
        {findings.length === 0 ? (
          <EmptyState>No open findings.</EmptyState>
        ) : (
          <ListPanel>
            {findings.slice(0, FINDING_LIMIT).map((finding) => (
              <FindingRow key={finding.id} finding={finding} briefing={briefing} />
            ))}
          </ListPanel>
        )}
      </section>

      {resolved.length > 0 || (briefing.close && briefing.close.completed.length > 0) ? (
        <section className="space-y-3">
          <SectionHeading title="Resolved" meta={resolved.length ? `${resolved.length}` : undefined} />
          {resolved.length > 0 ? (
            <ListPanel>
              {resolved.slice(0, RESOLVED_LIMIT).map((decision) => (
                <ResolvedRow key={decision.id} decision={decision} />
              ))}
            </ListPanel>
          ) : null}
          {briefing.close && briefing.close.completed.length > 0 ? (
            <p className="text-sm leading-6 text-mute">
              Close checklist complete: {briefing.close.completed.map(humanize).join(", ")}.
            </p>
          ) : null}
        </section>
      ) : null}

      <p className="text-xs leading-5 text-mute">{briefing.sandbox_notice}</p>
    </div>
  );
}

function AttentionRow({ decision }: { decision: DecisionBrief }) {
  const impact = money(decision.dollars_impact);
  const why = firstSentence(decision.rationale);
  const evidence = decision.policy_basis?.trim();
  const recommendation = recommendationFor(decision);

  return (
    <Link href="/decisions" className={cn(listRowInteractiveClassName, "sm:flex sm:items-start sm:justify-between sm:gap-4")}>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="alert">Needs approval</Badge>
          <Badge variant={riskVariant(decision.risk_level)}>{humanize(decision.risk_level)}</Badge>
          {decision.decision_type === "procurement" ? <Badge variant="sandbox">Sandbox</Badge> : null}
        </div>
        <h3 className="mt-2 font-serif text-lg text-ivory">{decisionTitle(decision.action, decision.decision_type)}</h3>
        {impact ? <p className="mt-1 font-serif text-xl tabular-nums text-ivory">{impact}</p> : null}
        {why ? <p className="mt-2 text-sm leading-6 text-mute">{why}</p> : null}
        {evidence ? (
          <p className="mt-2 truncate text-xs text-mute">
            <span className="text-ivory">Evidence. </span>
            {evidence}
          </p>
        ) : null}
        {recommendation ? <p className="mt-2 text-sm text-ivory">{recommendation}</p> : null}
      </div>
      <span className={cn(buttonVariants({ size: "sm" }), "mt-3 pointer-events-none shrink-0 sm:mt-0")}>
        Review
      </span>
    </Link>
  );
}

function FindingRow({ finding, briefing }: { finding: FindingBrief; briefing: Briefing }) {
  const memo = buildFindingMemo(finding, briefing, []);
  const why = firstSentence(finding.description);
  const status = findingStatusLabel(finding.status);

  return (
    <Link href={`/findings/${finding.id}`} className={listRowInteractiveClassName}>
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant={riskVariant(finding.severity)}>{humanize(finding.severity)}</Badge>
        <Badge variant={statusTone(status)}>{status}</Badge>
        {memo.approval ? <Badge variant={statusTone(memo.approval)}>{memo.approval}</Badge> : null}
      </div>
      <div className="mt-2 flex flex-wrap items-baseline justify-between gap-3">
        <h3 className="min-w-0 font-serif text-lg text-ivory">{finding.title}</h3>
        {memo.impact ? (
          <p className="shrink-0 font-serif text-xl tabular-nums text-ivory sm:w-28 sm:text-right">
            {memo.impact}
          </p>
        ) : null}
      </div>
      {why ? <p className="mt-1 text-sm leading-6 text-mute">{why}</p> : null}
    </Link>
  );
}

function ResolvedRow({ decision }: { decision: DecisionBrief }) {
  const impact = money(decision.dollars_impact);
  const why = firstSentence(decision.rationale);
  const status = decisionStatusLabel(decision.status, decision.requires_human_approval);

  return (
    <article className={listRowClassName}>
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant={statusTone(status)}>{status}</Badge>
        {impact ? <span className="font-mono text-xs tabular-nums text-ivory">{impact}</span> : null}
      </div>
      <h3 className="mt-2 font-serif text-lg text-ivory">{decisionTitle(decision.action, decision.decision_type)}</h3>
      {why ? <p className="mt-1 text-sm leading-6 text-mute">{why}</p> : null}
    </article>
  );
}
