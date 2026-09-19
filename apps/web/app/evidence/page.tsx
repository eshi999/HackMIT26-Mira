"use client";

import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { fetchBriefing, type Briefing } from "@/lib/api";

export default function EvidencePage() {
  const [briefing, setBriefing] = useState<Briefing | null>(null);
  const [q, setQ] = useState("");

  useEffect(() => {
    fetchBriefing().then(setBriefing);
  }, []);

  if (!briefing) {
    return <p className="text-mute">Indexing the inbox…</p>;
  }

  const needle = q.trim().toLowerCase();
  const docs = briefing.inbox.filter((d) =>
    needle ? `${d.filename} ${d.document_class}`.toLowerCase().includes(needle) : true,
  );
  const findings = briefing.findings.filter((f) =>
    needle ? `${f.title} ${f.description}`.toLowerCase().includes(needle) : true,
  );

  return (
    <div className="space-y-6">
      <h1 className="font-serif text-4xl">Evidence</h1>
      <p className="max-w-2xl text-mute">
        Elastic will own this index. Until then, SQL plus the local Dropbox-shaped inbox still
        surfaces documents, findings, and decisions. Search is the product, not a chat transcript.
      </p>
      <input
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="Find HelixCloud, policy, overdue…"
        className="w-full rounded-full border border-line bg-paper px-5 py-3 text-sm text-ivory outline-none placeholder:text-mute focus:border-brass/50"
      />
      <div className="grid gap-4 md:grid-cols-2">
        {docs.map((d) => (
          <Card key={d.id}>
            <CardContent className="pt-5">
              <Badge variant="mute">{d.document_class}</Badge>
              <h2 className="mt-2 font-mono text-sm">{d.filename}</h2>
              <p className="mt-1 text-xs text-mute">
                {d.storage_backend} · {d.storage_uri}
              </p>
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
