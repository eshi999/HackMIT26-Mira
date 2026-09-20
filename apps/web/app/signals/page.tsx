"use client";

import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { fetchSpaceSignals } from "@/lib/api";

type SpacePayload = {
  live?: boolean;
  narration?: string;
  grok?: string;
  voice_available?: boolean;
  affects_finance_truth?: boolean;
  launch?: { name?: string; date_utc?: string; provider?: string };
  iss?: { latitude?: number | string; longitude?: number | string; provider?: string };
  sources?: string[];
};

export default function SignalsPage() {
  const [payload, setPayload] = useState<SpacePayload | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchSpaceSignals()
      .then((data) => {
        if (!data) setError("External signals are unreachable.");
        else setPayload(data as SpacePayload);
      })
      .catch(() => setError("External signals are unreachable."));
  }, []);

  async function listen() {
    if (!payload?.narration) return;
    const token = process.env.NEXT_PUBLIC_MIRA_DEMO_TOKEN ?? "mira-demo-elena";
    const api = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    const res = await fetch(`${api}/api/v1/external-signals/space/speak`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ text: payload.narration, source: "space_narration" }),
    });
    if (!res.ok) return;
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    await new Audio(url).play();
  }

  if (error) return <p className="text-mute">{error}</p>;
  if (!payload) return <p className="text-mute">Fetching public space data…</p>;

  return (
    <div className="space-y-6">
      <Badge variant="ledger">SpaceXAI · isolated</Badge>
      <h1 className="font-serif text-4xl">External signals</h1>
      <p className="max-w-2xl text-mute">
        Public space observations plus optional Grok Voice. This rail does not write finance truth,
        savings, or decisions.
      </p>
      <Card>
        <CardHeader>
          <CardTitle>Next launch</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm text-mute">
          <p className="font-serif text-2xl text-ivory">{payload.launch?.name ?? "Unavailable"}</p>
          <p>{payload.launch?.date_utc ?? "No public time"}</p>
          <p>Source: {payload.launch?.provider}</p>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>ISS position</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm text-mute">
          <p className="font-serif text-2xl text-ivory">
            {payload.iss?.latitude ?? "—"}, {payload.iss?.longitude ?? "—"}
          </p>
          <p>Source: {payload.iss?.provider}</p>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center gap-2">
            <CardTitle>Grok Voice</CardTitle>
            <Badge variant={payload.grok === "live" ? "ledger" : "mute"}>{payload.grok}</Badge>
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-sm leading-relaxed text-ivory/80">{payload.narration}</p>
          {payload.voice_available ? (
            <Button size="sm" onClick={listen}>
              Speak
            </Button>
          ) : (
            <p className="text-xs text-mute">Grok Voice audio is optional. The script above is the fallback.</p>
          )}
          <p className="text-xs text-mute">
            Affects finance truth: {payload.affects_finance_truth ? "yes" : "no"}
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
