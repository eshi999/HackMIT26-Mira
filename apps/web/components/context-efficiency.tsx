"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { fetchMeasuredContext, type MeasuredContext } from "@/lib/api";

export function ContextEfficiency() {
  const [report, setReport] = useState<MeasuredContext | null>(null);
  const [unavailable, setUnavailable] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    fetchMeasuredContext()
      .then((next) => {
        if (controller.signal.aborted) return;
        if (!next) setUnavailable(true);
        else setReport(next);
      })
      .catch(() => {
        if (!controller.signal.aborted) setUnavailable(true);
      });
    return () => controller.abort();
  }, []);

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center gap-2">
          <CardTitle>Token Company · context budget</CardTitle>
          <Badge variant="ledger">measured</Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-2 text-sm text-mute" aria-live="polite">
        {unavailable ? (
          <p>Context measurements are unavailable. Start the API and run make token-eval.</p>
        ) : !report ? (
          <p>Measuring six finance scenarios…</p>
        ) : (
          <>
            <p className="text-ivory">
              {report.reduction_percent}% context reduction · {report.tokens_avoided.toLocaleString()}{" "}
              estimated tokens avoided
            </p>
            <p>
              {report.baseline.estimated_input_tokens.toLocaleString()} →{" "}
              {report.optimized.estimated_input_tokens.toLocaleString()} estimated tokens across{" "}
              {report.scenario_count} paired scenarios.
            </p>
            <p>
              Correctness retained: {report.correctness_retained_label} ·{" "}
              {report.correctness_retained ? "deterministic results identical" : "verification failed"}
            </p>
            <p>
              Source: {report.source ?? "make token-eval"} on a fresh Northstar seed. Estimates cover
              context only. Token Company is not connected as a live API.
            </p>
          </>
        )}
      </CardContent>
    </Card>
  );
}
