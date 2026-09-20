"use client";

import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  authorizePrecedent,
  fetchBriefing,
  fetchPrecedents,
  resolveDecision,
  type Briefing,
  type PrecedentRow,
} from "@/lib/api";
import { usd } from "@/lib/utils";

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
  const [busyId, setBusyId] = useState<string | null>(null);
  const [learning, setLearning] = useState(false);
  const [learnNote, setLearnNote] = useState<string | null>(null);

  async function reload() {
    const [next, rows] = await Promise.all([fetchBriefing(), fetchPrecedents()]);
    setBriefing(next);
    setPrecedents(rows);
  }

  useEffect(() => {
    reload();
  }, []);

  if (!briefing) {
    return <p className="text-mute">Loading the review queue…</p>;
  }

  async function onResolve(id: string, resolution: "approve" | "reject") {
    setBusyId(id);
    await resolveDecision(id, resolution);
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
    setLearnNote(
      result
        ? `Safe precedent recorded (${String(result.status)}). Comparable AWS invoices can now auto-process; a new vendor still escalates.`
        : "Precedent was not recorded. Elena's demo token is required.",
    );
    await reload();
    setLearning(false);
  }

  const exceptions = briefing.pending_decisions.filter((d) => d.requires_human_approval);

  return (
    <div className="space-y-6">
      <h1 className="font-serif text-4xl">Human review</h1>
      <p className="max-w-2xl text-mute">
        Maximor path: exception → human review → safe precedent. Approve or reject updates
        canonical state. Learning uses typed authorization, not free-text chat.
      </p>
      <div className="grid gap-3 md:grid-cols-3">
        {[
          { n: "1", t: "Exception", d: `${exceptions.length} packets need a human` },
          { n: "2", t: "Review", d: "Approve or reject with policy + authority" },
          { n: "3", t: "Learn", d: "Elena authorizes a scoped AWS $12k precedent" },
        ].map((step) => (
          <Card key={step.n}>
            <CardContent className="pt-5">
              <Badge variant="ledger">{step.n}</Badge>
              <h2 className="mt-2 font-serif text-lg">{step.t}</h2>
              <p className="mt-1 text-xs text-mute">{step.d}</p>
            </CardContent>
          </Card>
        ))}
      </div>
      <div className="space-y-4">
        {briefing.pending_decisions.map((d) => (
          <Card key={d.id}>
            <CardContent className="space-y-3 pt-5">
              <div className="flex flex-wrap gap-2">
                <Badge variant={d.requires_human_approval ? "alert" : "ledger"}>{d.status}</Badge>
                <Badge variant="mute">{d.decision_type}</Badge>
                <Badge variant="mute">{d.risk_level}</Badge>
                {d.dollars_impact ? <Badge variant="default">{usd(d.dollars_impact)}</Badge> : null}
              </div>
              <h2 className="font-serif text-2xl">{d.action.replaceAll("_", " ")}</h2>
              <p className="text-sm leading-relaxed text-mute">{d.rationale}</p>
              <p className="text-xs text-ivory/80">
                Policy: {d.policy_basis}
                <br />
                Authority: {d.authority_basis}
              </p>
              {d.requires_human_approval && d.status === "awaiting_human" ? (
                <div className="flex flex-wrap gap-2 pt-1">
                  <Button size="sm" disabled={busyId === d.id} onClick={() => onResolve(d.id, "approve")}>
                    Approve
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={busyId === d.id}
                    onClick={() => onResolve(d.id, "reject")}
                  >
                    Reject
                  </Button>
                  <Button size="sm" variant="ghost" disabled={learning} onClick={() => onLearn(d.id)}>
                    Learn AWS $12k precedent
                  </Button>
                </div>
              ) : null}
            </CardContent>
          </Card>
        ))}
      </div>
      {learnNote ? <p className="text-sm text-ledger">{learnNote}</p> : null}
      <section>
        <h2 className="mb-3 font-serif text-2xl">Active precedent</h2>
        <div className="space-y-3">
          {precedents.map((row) => (
            <Card key={row.id}>
              <CardContent className="pt-5">
                <div className="flex flex-wrap gap-2">
                  <Badge variant={row.status === "active" ? "ledger" : "mute"}>{row.status}</Badge>
                  <Badge variant="mute">{row.outcome}</Badge>
                </div>
                <p className="mt-2 text-sm text-ivory">{row.summary}</p>
                <p className="mt-1 text-xs text-mute">
                  {row.scope} · {row.authorizer ?? "unauthored"} · {row.period}
                </p>
              </CardContent>
            </Card>
          ))}
        </div>
      </section>
    </div>
  );
}
