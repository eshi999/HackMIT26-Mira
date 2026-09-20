"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

type Efficiency = {
  tokens_avoided: number;
  reduction_percent: string;
  correctness_retained: boolean;
  baseline: { estimated_input_tokens: number };
  optimized: { estimated_input_tokens: number };
  scenarios: { optimized: { mandatory_over_budget: boolean } }[];
};

export function ContextEfficiency() {
  const [report, setReport] = useState<Efficiency | null>(null);
  const [unavailable, setUnavailable] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    const base = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    fetch(`${base}/api/v1/context/efficiency`, {
      headers: { Authorization: "Bearer mira-demo-elena" },
      cache: "no-store",
      signal: controller.signal,
    })
      .then((response) => {
        if (!response.ok) throw new Error("Measurement unavailable");
        return response.json();
      })
      .then(setReport)
      .catch(() => { if (!controller.signal.aborted) setUnavailable(true); });
    return () => controller.abort();
  }, []);

  return (
    <Card>
      <CardHeader><CardTitle>AI context efficiency</CardTitle></CardHeader>
      <CardContent className="space-y-2 text-sm text-mute" aria-live="polite">
        {unavailable ? <p>Context measurements are unavailable. Start the API to run the comparison.</p> : !report ? (
          <p>Measuring six finance scenarios…</p>
        ) : (
          <>
            <p className="text-ivory">{report.reduction_percent}% less context · {report.tokens_avoided.toLocaleString()} estimated input tokens avoided</p>
            <p>{report.baseline.estimated_input_tokens.toLocaleString()} → {report.optimized.estimated_input_tokens.toLocaleString()} estimated tokens across six paired scenarios.</p>
            <p>Deterministic financial results: {report.correctness_retained ? "identical in both modes" : "verification failed"}.</p>
            <p>{report.scenarios.filter((row) => row.optimized.mandatory_over_budget).length} scenarios retain mandatory facts above the target budget.</p>
            <p>Measured on the current demo snapshot against a full-snapshot baseline. Estimates cover context only, not billed usage. Token Company is not connected.</p>
          </>
        )}
      </CardContent>
    </Card>
  );
}
