"use client";

import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorState } from "@/components/ui/error-state";
import { PageSkeleton } from "@/components/ui/skeleton";
import { fetchSpaceSignals } from "@/lib/api";
import { formatCoord, formatDateTime, humanize, statusTone } from "@/lib/display";

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
        if (!data) {
          console.error("External signals unavailable");
          setError("External signals are unreachable.");
        } else setPayload(data as SpacePayload);
      })
      .catch((err) => {
        console.error("Failed to load external signals", err);
        setError("External signals are unreachable.");
      });
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
    if (!res.ok) {
      console.error("Space narration playback failed", res.status);
      return;
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    await new Audio(url).play();
  }

  if (error) return <ErrorState title="Signals are offline">{error}</ErrorState>;
  if (!payload) return <PageSkeleton label="Loading public space data" />;

  const launchTime = formatDateTime(payload.launch?.date_utc);
  const latitude = formatCoord(payload.iss?.latitude);
  const longitude = formatCoord(payload.iss?.longitude);
  const grokLabel = payload.grok ? humanize(payload.grok) : "Unavailable";
  const position =
    latitude && longitude ? `${latitude}, ${longitude}` : latitude ?? longitude ?? "Unavailable";

  return (
    <div className="space-y-8">
      <Badge variant="ledger">SpaceXAI · isolated</Badge>

      <Card>
        <CardHeader>
          <CardTitle>Next launch</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm leading-6 text-mute">
          <p className="font-serif text-2xl text-ivory">{payload.launch?.name ?? "Unavailable"}</p>
          <p>{launchTime ?? "No public time"}</p>
          {payload.launch?.provider ? <p>Source: {payload.launch.provider}</p> : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>ISS position</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm leading-6 text-mute">
          <p className="font-serif text-2xl tabular-nums text-ivory">{position}</p>
          {payload.iss?.provider ? <p>Source: {payload.iss.provider}</p> : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center gap-2">
            <CardTitle>Grok Voice</CardTitle>
            <Badge variant={statusTone(grokLabel)}>{grokLabel}</Badge>
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          {payload.narration ? (
            <p className="text-sm leading-6 text-ivory/80">{payload.narration}</p>
          ) : (
            <p className="text-sm leading-6 text-mute">No narration available.</p>
          )}
          {payload.voice_available ? (
            <Button size="sm" onClick={listen} disabled={!payload.narration}>
              Speak
            </Button>
          ) : (
            <p className="text-xs leading-5 text-mute">
              Grok Voice audio is optional. The script above is the fallback.
            </p>
          )}
          <p className="text-xs leading-5 text-mute">
            {payload.affects_finance_truth
              ? "This rail is marked as affecting finance truth."
              : "This rail does not write finance truth, savings, or decisions."}
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
