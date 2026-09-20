"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { Input } from "@/components/ui/input";
import { ListPanel, listRowClassName } from "@/components/ui/list-panel";
import { PageSkeleton, Skeleton } from "@/components/ui/skeleton";
import { fetchBriefing, searchEvidence, type Briefing, type EvidenceSearch } from "@/lib/api";
import { humanize } from "@/lib/display";

export default function EvidencePage() {
  return (
    <Suspense fallback={<PageSkeleton label="Indexing the inbox" variant="list" />}>
      <EvidencePageBody />
    </Suspense>
  );
}

function EvidencePageBody() {
  const searchParams = useSearchParams();
  const initial = searchParams.get("q") ?? "";
  const [briefing, setBriefing] = useState<Briefing | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [q, setQ] = useState(initial);
  const [search, setSearch] = useState<EvidenceSearch | null>(null);
  const [searching, setSearching] = useState(false);

  useEffect(() => {
    fetchBriefing()
      .then((data) => {
        if (!data) {
          console.error("Briefing unavailable for evidence");
          setError("Evidence is unavailable. Start the API on :8000.");
        } else setBriefing(data);
      })
      .catch((err) => {
        console.error("Failed to load evidence", err);
        setError("Evidence is unavailable.");
      });
  }, []);

  useEffect(() => {
    setQ(initial);
  }, [initial]);

  useEffect(() => {
    const needle = q.trim();
    if (needle.length < 2) {
      setSearch(null);
      setSearching(false);
      return;
    }
    setSearching(true);
    const handle = window.setTimeout(() => {
      searchEvidence(needle)
        .then((result) => {
          setSearch(result);
          setSearching(false);
        })
        .catch((err) => {
          console.error("Evidence search failed", err);
          setSearch(null);
          setSearching(false);
        });
    }, 250);
    return () => window.clearTimeout(handle);
  }, [q]);

  if (error) {
    return <ErrorState title="Evidence is offline">{error}</ErrorState>;
  }

  if (!briefing) {
    return <PageSkeleton label="Indexing the inbox" variant="list" />;
  }

  const needle = q.trim().toLowerCase();
  const docs = briefing.inbox.filter((d) =>
    needle ? `${d.filename} ${d.document_class} ${d.lineage ?? ""}`.toLowerCase().includes(needle) : true,
  );
  const retrievalLabel = search?.retrieval_source === "elastic" ? "Elastic" : "Search";

  return (
    <div className="space-y-8">
      <Input
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="Find HelixCloud, policy, overdue…"
        aria-label="Search evidence"
        className="sm:max-w-md"
      />

      {searching ? (
        <div className="space-y-3" aria-busy="true" aria-live="polite">
          <span className="sr-only">Searching evidence</span>
          <Skeleton className="h-24 w-full" />
        </div>
      ) : null}

      {!searching && q.trim().length >= 2 && !search ? (
        <EmptyState>Search is unavailable right now.</EmptyState>
      ) : null}

      {!searching && search ? (
        <Card>
          <CardContent className="space-y-3 pt-5">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant={search.retrieval_source === "elastic" ? "ledger" : "mute"}>{retrievalLabel}</Badge>
              <span className="text-xs text-mute">
                {search.hit_count} retrieved hit{search.hit_count === 1 ? "" : "s"}
              </span>
            </div>
            {search.explanation ? <p className="text-sm leading-6 text-mute">{search.explanation}</p> : null}
            {search.hits.length === 0 ? (
              <p className="text-sm leading-6 text-mute">No retrieved hits for this query.</p>
            ) : (
              <ul className="space-y-3">
                {search.hits.slice(0, 6).map((hit) => (
                  <li key={`${hit.object_type}-${hit.object_id}-${hit.title}`} className="text-sm leading-6">
                    <span className="text-ivory">{hit.title}</span>
                    <span className="text-mute">
                      {" "}
                      · {humanize(hit.object_type)}
                      {hit.source_system ? ` · ${hit.source_system}` : ""}
                    </span>
                    {hit.snippet ? <p className="text-xs leading-5 text-mute">{hit.snippet}</p> : null}
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      ) : null}

      {docs.length === 0 ? (
        <EmptyState>
          {briefing.inbox.length === 0 ? "No source documents in the inbox." : "No documents match this search."}
        </EmptyState>
      ) : (
        <ListPanel>
          {docs.map((d) => (
            <article key={d.id} className={listRowClassName}>
              <Badge variant="mute">{humanize(d.document_class)}</Badge>
              <h2 className="mt-2 font-serif text-lg text-ivory">{d.filename}</h2>
              <p className="mt-1 text-xs leading-5 text-mute">{d.lineage ?? humanize(d.storage_backend)}</p>
              {d.evidence_title ? (
                <p className="mt-2 text-xs leading-5 text-ivory/80">Linked evidence: {d.evidence_title}</p>
              ) : null}
            </article>
          ))}
        </ListPanel>
      )}
    </div>
  );
}
