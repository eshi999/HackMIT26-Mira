"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { FilterChip } from "@/components/ui/filter-chip";
import { Input } from "@/components/ui/input";
import { ListPanel, listRowInteractiveClassName } from "@/components/ui/list-panel";
import { PageSkeleton } from "@/components/ui/skeleton";
import { fetchBriefing, type Briefing } from "@/lib/api";
import { firstSentence, findingStatusLabel, formatDate, humanize, riskVariant, statusTone } from "@/lib/display";
import { buildFindingMemo, sortFindings } from "@/lib/finding-context";

export default function FindingsPage() {
  const [briefing, setBriefing] = useState<Briefing | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [focus, setFocus] = useState<"all" | "urgent">("all");

  useEffect(() => {
    fetchBriefing()
      .then((data) => {
        if (!data) {
          console.error("Briefing unavailable for findings");
          setError("Findings are unavailable. Start the API on :8000.");
        } else setBriefing(data);
      })
      .catch((err) => {
        console.error("Failed to load findings", err);
        setError("Findings are unavailable.");
      });
  }, []);

  const rows = useMemo(() => {
    if (!briefing) return [];
    const needle = query.trim().toLowerCase();
    return sortFindings(briefing.findings).filter((finding) => {
      if (focus === "urgent" && finding.severity !== "critical" && finding.severity !== "high") {
        return false;
      }
      if (!needle) return true;
      return `${finding.title} ${finding.description} ${finding.finding_type}`.toLowerCase().includes(needle);
    });
  }, [briefing, query, focus]);

  if (error) {
    return <ErrorState title="Findings are offline">{error}</ErrorState>;
  }

  if (!briefing) {
    return <PageSkeleton label="Loading findings" variant="list" />;
  }

  const emptyMessage =
    briefing.findings.length === 0 ? "No findings right now." : "No findings match this search.";

  return (
    <div className="space-y-8">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <Input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search title, vendor, invoice…"
          aria-label="Search findings"
          className="sm:max-w-md"
        />
        <div className="flex flex-wrap gap-2">
          <FilterChip active={focus === "all"} onClick={() => setFocus("all")}>
            All {briefing.findings.length}
          </FilterChip>
          <FilterChip active={focus === "urgent"} onClick={() => setFocus("urgent")}>
            Critical & high
          </FilterChip>
        </div>
      </div>

      {rows.length === 0 ? (
        <EmptyState>{emptyMessage}</EmptyState>
      ) : (
        <ListPanel>
          {rows.map((finding) => {
            const memo = buildFindingMemo(finding, briefing, []);
            const due = memo.invoices.find((invoice) => invoice.due_date)?.due_date;
            const status = findingStatusLabel(finding.status);
            const dueLabel = formatDate(due);
            return (
              <Link key={finding.id} href={`/findings/${finding.id}`} className={listRowInteractiveClassName}>
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant={riskVariant(finding.severity)}>{humanize(finding.severity)}</Badge>
                  <Badge variant={statusTone(status)}>{status}</Badge>
                  {memo.approval ? <Badge variant={statusTone(memo.approval)}>{memo.approval}</Badge> : null}
                  <Badge variant="mute">{humanize(finding.finding_type)}</Badge>
                </div>
                <div className="mt-2 flex flex-wrap items-baseline justify-between gap-3">
                  <h2 className="min-w-0 font-serif text-lg text-ivory">{finding.title}</h2>
                  {memo.impact ? (
                    <p className="shrink-0 font-serif text-xl tabular-nums text-ivory sm:w-28 sm:text-right">
                      {memo.impact}
                    </p>
                  ) : null}
                </div>
                <p className="mt-1 text-sm leading-6 text-mute">{firstSentence(finding.description)}</p>
                {dueLabel ? <p className="mt-1 text-xs text-mute">Due {dueLabel}</p> : null}
              </Link>
            );
          })}
        </ListPanel>
      )}
    </div>
  );
}
