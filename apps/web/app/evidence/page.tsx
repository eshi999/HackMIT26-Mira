"use client";

import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import {
  fetchBriefing,
  searchEvidence,
  type Briefing,
  type EvidenceSearch,
} from "@/lib/api";

export default function EvidencePage() {
  const [briefing, setBriefing] = useState<Briefing | null>(null);
  const [q, setQ] = useState("");
  const [search, setSearch] = useState<EvidenceSearch | null>(null);

  useEffect(() => {
    fetchBriefing().then(setBriefing);
  }, []);

  useEffect(() => {
    const needle = q.trim();
    if (needle.length < 2) {
      setSearch(null);
      return;
    }
    const handle = window.setTimeout(() => {
      searchEvidence(needle).then(setSearch);
    }, 250);
    return () => window.clearTimeout(handle);
  }, [q]);

  if (!briefing) {
    return <p className="text-mute">Indexing the inbox…</p>;
  }

  const needle = q.trim().toLowerCase();
  const docs = briefing.inbox.filter((d) =>
    needle ? `${d.filename} ${d.document_class} ${d.lineage ?? ""}`.toLowerCase().includes(needle) : true,
  );
  const findings = briefing.findings.filter((f) =>
    needle ? `${f.title} ${f.description}`.toLowerCase().includes(needle) : true,
  );

  return (
    <div className="space-y-6">
      <h1 className="font-serif text-4xl">Evidence</h1>
      <p className="max-w-2xl text-mute">
        Dropbox lineage stays on the document. Elastic contributes retrieved hits when the cluster
        is live; otherwise the demo projection still searches Northstar evidence.
      </p>
      <input
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="Find HelixCloud, policy, overdue…"
        className="w-full rounded-full border border-line bg-paper px-5 py-3 text-sm text-ivory outline-none placeholder:text-mute focus:border-brass/50"
      />
      {search ? (
        <Card>
          <CardContent className="space-y-2 pt-5">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="ledger">Elastic</Badge>
              <Badge variant="mute">{search.retrieval_source}</Badge>
              <span className="text-xs text-mute">
                {search.hit_count} retrieved hit{search.hit_count === 1 ? "" : "s"}
              </span>
            </div>
            <p className="text-sm text-mute">{search.explanation}</p>
            <ul className="space-y-2">
              {search.hits.slice(0, 6).map((hit) => (
                <li key={`${hit.object_type}-${hit.object_id}-${hit.title}`} className="text-sm">
                  <span className="text-ivory">{hit.title}</span>
                  <span className="text-mute">
                    {" "}
                    · {hit.object_type} · {hit.source_system}
                  </span>
                  {hit.snippet ? <p className="text-xs text-mute">{hit.snippet}</p> : null}
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      ) : null}
      <div className="grid gap-4 md:grid-cols-2">
        {docs.map((d) => (
          <Card key={d.id}>
            <CardContent className="pt-5">
              <Badge variant="mute">{d.document_class}</Badge>
              <h2 className="mt-2 font-mono text-sm">{d.filename}</h2>
              <p className="mt-1 text-xs text-mute">{d.lineage ?? `${d.storage_backend} · ${d.storage_uri}`}</p>
              {d.evidence_title ? (
                <p className="mt-2 text-xs text-ivory/80">Linked evidence: {d.evidence_title}</p>
              ) : null}
            </CardContent>
          </Card>
        ))}
        {findings.map((f) => (
          <Card key={f.id}>
            <CardContent className="pt-5">
              <Badge variant="alert">{f.finding_type}</Badge>
              <h2 className="mt-2 font-serif text-lg">{f.title}</h2>
              <p className="mt-1 text-sm text-mute">{f.description}</p>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
