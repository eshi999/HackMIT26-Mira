"use client";

import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { fetchBriefing, type Briefing } from "@/lib/api";
import { hours, usd } from "@/lib/utils";

export function CommandCenter() {
  const [briefing, setBriefing] = useState<Briefing | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchBriefing()
      .then((data) => {
        if (!data) setError("Mira's office is not reachable. Start the API on :8000.");
        else setBriefing(data);
      })
      .catch(() => setError("Mira's office is not reachable."));
  }, []);

  if (error) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Mira is offline</CardTitle>
        </CardHeader>
        <CardContent className="text-mute">
          {error} The command center does not fall back to a chatbot.
        </CardContent>
      </Card>
    );
  }

  if (!briefing) {
    return <p className="text-mute">Opening the office…</p>;
  }

  const cash = Number(briefing.cash.amount);
  const ap = Number(briefing.open_ap);
  const chart = [
    { name: "Cash", value: cash },
    { name: "Open AP", value: ap },
  ];
  const needsYou = briefing.pending_decisions.filter((d) => d.requires_human_approval);

  return (
    <div className="space-y-8">
      <section className="grid gap-8 lg:grid-cols-[1.4fr_0.8fr]">
        <div>
          <Badge variant="ledger">Employee · not a chatbot</Badge>
          <h1 className="mt-4 max-w-3xl font-serif text-4xl leading-tight text-ivory md:text-5xl">
            {briefing.headline}
          </h1>
          <p className="mt-5 max-w-2xl text-base leading-relaxed text-mute">{briefing.narrative}</p>
        </div>
        <Card>
          <CardHeader>
            <CardTitle className="text-base text-mute">Overnight scoreboard</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <div className="text-[11px] uppercase tracking-[0.18em] text-mute">Dollars protected</div>
              <div className="font-serif text-3xl text-ledger">
                {usd(briefing.savings.dollars_protected)}
              </div>
            </div>
            <div>
              <div className="text-[11px] uppercase tracking-[0.18em] text-mute">Dollars saved</div>
              <div className="font-serif text-3xl text-ivory">
                {usd(briefing.savings.dollars_saved ?? 0)}
              </div>
            </div>
            <div>
              <div className="text-[11px] uppercase tracking-[0.18em] text-mute">Hours returned</div>
              <div className="font-serif text-3xl text-ivory">
                {hours(briefing.savings.hours_saved)}
              </div>
            </div>
            <div className="text-xs text-mute">
              Workflow SavingsEvent rows · {briefing.savings.source ?? "runtime"} · {briefing.savings.period}
            </div>
          </CardContent>
        </Card>
      </section>

      <section className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader>
            <CardTitle className="text-sm text-mute">Autonomous completion</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="font-serif text-3xl">
              {Number(briefing.autonomous_completion_rate ?? 0).toFixed(0)}
            </div>
            <p className="mt-1 text-xs text-mute">Autonomy score from the evaluation engine, 0–100.</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-sm text-mute">Reconciliation rate</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="font-serif text-3xl">
              {(Number(briefing.reconciliation_rate ?? 0) * 100).toFixed(0)}%
            </div>
            <p className="mt-1 text-xs text-mute">Bank feed matched without forced pairing.</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-sm text-mute">Open incidents</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="font-serif text-3xl">{briefing.open_incidents ?? 0}</div>
            <p className="mt-1 text-xs text-mute">Risk-engine incidents still open.</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-sm text-mute">Gates</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="font-serif text-3xl">{briefing.pending_approvals ?? needsYou.length}</div>
            <p className="mt-1 text-xs text-mute">
              Pending approvals · {briefing.blocked_payments ?? 0} blocked payments
            </p>
          </CardContent>
        </Card>
      </section>

      {briefing.close ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm text-mute">September close</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="font-serif text-3xl">
              {(Number(briefing.close.completion_pct) * 100).toFixed(0)}%
            </div>
            <p className="mt-1 text-xs text-mute">
              {briefing.close.completed.length} complete · {briefing.close.blocked.length} blocked · audit{" "}
              {briefing.close.audit_status}
            </p>
          </CardContent>
        </Card>
      ) : null}

      <section className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle className="text-sm text-mute">Operating cash</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="font-serif text-3xl">{usd(cash)}</div>
            <p className="mt-1 text-xs text-mute">{briefing.cash.account_name}</p>
            <div className="mt-4 h-28">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chart}>
                  <XAxis dataKey="name" stroke="#8B93A0" fontSize={11} tickLine={false} axisLine={false} />
                  <YAxis hide />
                  <Tooltip
                    formatter={(v: number) => usd(v)}
                    contentStyle={{ background: "#10151C", border: "1px solid #243040" }}
                  />
                  <Bar dataKey="value" fill="#C4A574" radius={[6, 6, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-sm text-mute">Inbox recovered</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="font-serif text-3xl">{briefing.documents_ingested}</div>
            <p className="mt-1 text-xs text-mute">
              Messy Dropbox-shaped dump classified into canonical documents.
            </p>
            <ul className="mt-4 space-y-1 font-mono text-[11px] text-mute">
              {briefing.inbox.slice(0, 4).map((doc) => (
                <li key={doc.id} className="truncate">
                  {doc.document_class} · {doc.filename}
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-sm text-mute">Public signal</CardTitle>
          </CardHeader>
          <CardContent>
            {briefing.signals.slice(0, 1).map((s) => (
              <div key={s.series_id}>
                <div className="font-serif text-3xl">
                  {Number(s.value).toFixed(2)}
                  <span className="ml-2 text-lg text-mute">%</span>
                </div>
                <p className="mt-1 text-xs text-mute">
                  {s.title} · {s.source} {s.series_id} · {s.as_of}
                </p>
                <p className="mt-3 text-sm leading-relaxed text-ivory/80">{s.note}</p>
              </div>
            ))}
          </CardContent>
        </Card>
      </section>

      <section className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
        <div>
          <h2 className="mb-3 font-serif text-2xl">Needs you</h2>
          <div className="space-y-3">
            {needsYou.map((d) => (
              <Card key={d.id} className="border-brass/30">
                <CardContent className="pt-5">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant="alert">Human review</Badge>
                    <Badge variant="sandbox">Sandbox if purchased</Badge>
                    <Badge variant="mute">{d.risk_level} risk</Badge>
                    <Badge variant="mute">conf {Number(d.confidence_score).toFixed(2)}</Badge>
                  </div>
                  <h3 className="mt-3 font-serif text-xl">{d.action.replaceAll("_", " ")}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-mute">{d.rationale}</p>
                  <dl className="mt-4 grid gap-2 text-xs text-mute">
                    <div>
                      <span className="text-ivory">Policy. </span>
                      {d.policy_basis}
                    </div>
                    <div>
                      <span className="text-ivory">Authority. </span>
                      {d.authority_basis}
                    </div>
                  </dl>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
        <div>
          <h2 className="mb-3 font-serif text-2xl">What I already did</h2>
          <div className="space-y-3">
            {briefing.findings.map((f) => (
              <Card key={f.id}>
                <CardContent className="pt-5">
                  <Badge variant={f.severity === "high" ? "alert" : "ledger"}>{f.finding_type}</Badge>
                  <h3 className="mt-2 font-serif text-lg">{f.title}</h3>
                  <p className="mt-2 text-sm text-mute">{f.description}</p>
                </CardContent>
              </Card>
            ))}
            {briefing.invoices
              .filter((i) => i.is_duplicate_suspect)
              .map((i) => (
                <Card key={i.id}>
                  <CardContent className="pt-5">
                    <Badge variant="alert">Duplicate blocked</Badge>
                    <p className="mt-2 text-sm">
                      {i.vendor_name} {i.invoice_number} · {usd(i.total)}
                    </p>
                  </CardContent>
                </Card>
              ))}
          </div>
        </div>
      </section>
      <p className="text-xs text-mute">{briefing.sandbox_notice}</p>
    </div>
  );
}
