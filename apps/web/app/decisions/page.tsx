"use client";

import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { fetchBriefing, type Briefing } from "@/lib/api";
import { usd } from "@/lib/utils";

export default function DecisionsPage() {
  const [briefing, setBriefing] = useState<Briefing | null>(null);

  useEffect(() => {
    fetchBriefing().then(setBriefing);
  }, []);

  if (!briefing) {
    return <p className="text-mute">Loading the review queue…</p>;
  }

  return (
    <div className="space-y-6">
      <h1 className="font-serif text-4xl">Human review</h1>
      <p className="max-w-2xl text-mute">
        High risk or low confidence stops here. Every packet has evidence, a policy basis, and an
        authority basis. Mira does not hide behind a prompt box.
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
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
