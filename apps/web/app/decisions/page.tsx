"use client";

import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { fetchBriefing, resolveDecision, type Briefing } from "@/lib/api";
import { usd } from "@/lib/utils";

export default function DecisionsPage() {
  const [briefing, setBriefing] = useState<Briefing | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  useEffect(() => {
    fetchBriefing().then(setBriefing);
  }, []);

  if (!briefing) {
    return <p className="text-mute">Loading the review queue…</p>;
  }

  async function onResolve(id: string, resolution: "approve" | "reject") {
    setBusyId(id);
    await resolveDecision(id, resolution);
    const next = await fetchBriefing();
    setBriefing(next);
    setBusyId(null);
  }

  return (
    <div className="space-y-6">
      <h1 className="font-serif text-4xl">Human review</h1>
      <p className="max-w-2xl text-mute">
        High risk or low confidence stops here. Every packet has evidence, a policy basis, and an
        authority basis. Approve or reject updates canonical state and the audit log. It does not
        claim a payment moved.
      </p>
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
                <div className="flex gap-2 pt-1">
                  <Button
                    size="sm"
                    disabled={busyId === d.id}
                    onClick={() => onResolve(d.id, "approve")}
                  >
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
                </div>
              ) : null}
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
