"use client";

import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { PageSkeleton } from "@/components/ui/skeleton";
import { SectionHeading } from "@/components/ui/section-heading";
import {
  authorizePrecedent,
  fetchBriefing,
  fetchPrecedents,
  resolveDecision,
  type Briefing,
  type PrecedentRow,
} from "@/lib/api";
import {
  decisionStatusLabel,
  decisionTitle,
  humanize,
  money,
  precedentStatusLabel,
  riskVariant,
  statusTone,
} from "@/lib/display";

const AWS_PRECEDENT = {
  summary: "AWS infrastructure invoices under $12,000 are pre-approved.",
  reusable_rule:
    "AWS infrastructure invoices under $12,000 are pre-approved without secondary review.",
  outcome: "pre_approved",
  scope: "aws_infrastructure_spend",
  vendor: "Amazon Web Services",
  category: "infrastructure",
  amount_threshold: "12000.00",
  effective_date: "2026-09-19",
};

export default function DecisionsPage() {
  const [briefing, setBriefing] = useState<Briefing | null>(null);
  const [precedents, setPrecedents] = useState<PrecedentRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [learning, setLearning] = useState(false);
  const [learnNote, setLearnNote] = useState<string | null>(null);

  async function reload() {
    const [next, rows] = await Promise.all([fetchBriefing(), fetchPrecedents()]);
    if (!next) {
      console.error("Briefing unavailable for approvals");
      setError("Approvals are unavailable. Start the API on :8000.");
    } else {
      setError(null);
      setBriefing(next);
    }
    setPrecedents(rows);
  }

  useEffect(() => {
    reload().catch((err) => {
      console.error("Failed to load approvals", err);
      setError("Approvals are unavailable.");
    });
  }, []);

  if (error && !briefing) {
    return <ErrorState title="Approvals are offline">{error}</ErrorState>;
  }

  if (!briefing) {
    return <PageSkeleton label="Loading the review queue" variant="list" />;
  }

  async function onResolve(id: string, resolution: "approve" | "reject") {
    setBusyId(id);
    const result = await resolveDecision(id, resolution);
    if (!result) console.error("Decision resolve failed", id, resolution);
    await reload();
    setBusyId(null);
  }

  async function onLearn(decisionId: string) {
    setLearning(true);
    setLearnNote(null);
    const result = await authorizePrecedent({
      ...AWS_PRECEDENT,
      evidence: [`human-review:${decisionId}`, "typed-authorization:elena-cfo"],
    });
    const recordedStatus =
      result && typeof result.status === "string" ? precedentStatusLabel(result.status) : null;
    setLearnNote(
      result
        ? `Safe precedent recorded${recordedStatus ? ` · ${recordedStatus}` : ""}. Comparable AWS invoices can now auto-process; a new vendor still escalates.`
        : "Precedent was not recorded. Elena's demo token is required.",
    );
    await reload();
    setLearning(false);
  }

  const exceptions = briefing.pending_decisions.filter((d) => d.requires_human_approval);

  return (
    <div className="space-y-8">
      <div className="grid gap-3 md:grid-cols-3">
        {[
          { n: "1", t: "Exception", d: `${exceptions.length} packets need a human` },
          { n: "2", t: "Review", d: "Approve or reject with policy + authority" },
          { n: "3", t: "Learn", d: "Elena authorizes a scoped AWS $12k precedent" },
        ].map((step) => (
          <Card key={step.n}>
            <CardContent className="pt-5">
              <Badge variant="ledger">{step.n}</Badge>
              <h2 className="mt-2 font-serif text-lg text-ivory">{step.t}</h2>
              <p className="mt-1 text-xs leading-5 text-mute">{step.d}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      {briefing.pending_decisions.length === 0 ? (
        <EmptyState>No items in the review queue.</EmptyState>
      ) : (
        <div className="space-y-4">
          {briefing.pending_decisions.map((d) => {
            const status = decisionStatusLabel(d.status, d.requires_human_approval);
            const impact = money(d.dollars_impact);
            const waiting = d.requires_human_approval && d.status === "awaiting_human";
            return (
              <Card key={d.id}>
                <CardContent className="space-y-3 pt-5">
                  <div className="flex flex-wrap gap-2">
                    <Badge variant={statusTone(status)}>{status}</Badge>
                    <Badge variant="mute">{humanize(d.decision_type)}</Badge>
                    <Badge variant={riskVariant(d.risk_level)}>{humanize(d.risk_level)}</Badge>
                    {impact ? <Badge variant="default">{impact}</Badge> : null}
                  </div>
                  <h2 className="font-serif text-lg text-ivory">{decisionTitle(d.action, d.decision_type)}</h2>
                  <p className="text-sm leading-6 text-mute">{d.rationale}</p>
                  <p className="text-xs leading-5 text-ivory/80">
                    Policy: {d.policy_basis}
                    <br />
                    Authority: {d.authority_basis}
                  </p>
                  {waiting ? (
                    <div className="flex flex-wrap gap-2 pt-1">
                      <Button type="button" size="sm" disabled={busyId === d.id} onClick={() => onResolve(d.id, "approve")}>
                        {busyId === d.id ? "Saving…" : "Approve"}
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        disabled={busyId === d.id}
                        onClick={() => onResolve(d.id, "reject")}
                      >
                        Reject
                      </Button>
                      <Button type="button" size="sm" variant="ghost" disabled={learning} onClick={() => onLearn(d.id)}>
                        Learn AWS $12k precedent
                      </Button>
                    </div>
                  ) : null}
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      {learnNote ? (
        <p className={`text-sm leading-6 ${learnNote.includes("not recorded") ? "text-alert" : "text-ledger"}`}>
          {learnNote}
        </p>
      ) : null}

      <section className="space-y-3">
        <SectionHeading title="Active precedent" meta={precedents.length ? `${precedents.length}` : undefined} />
        {precedents.length === 0 ? (
          <EmptyState>No active precedent yet.</EmptyState>
        ) : (
          <div className="space-y-3">
            {precedents.map((row) => {
              const status = precedentStatusLabel(row.status);
              return (
                <Card key={row.id}>
                  <CardContent className="pt-5">
                    <div className="flex flex-wrap gap-2">
                      <Badge variant={statusTone(status)}>{status}</Badge>
                      <Badge variant="mute">{humanize(row.outcome)}</Badge>
                    </div>
                    <p className="mt-2 text-sm leading-6 text-ivory">{row.summary}</p>
                    <p className="mt-1 text-xs leading-5 text-mute">
                      {humanize(row.scope)}
                      {row.authorizer ? ` · ${row.authorizer}` : ""}
                      {row.period ? ` · ${row.period}` : ""}
                    </p>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
}
