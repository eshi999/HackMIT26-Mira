import { OfficeGraph } from "@/components/office-graph";
import { Badge } from "@/components/ui/badge";

export default function OfficePage() {
  return (
    <div className="space-y-6">
      <Badge variant="ledger">One face to the company</Badge>
      <h1 className="font-serif text-4xl text-ivory">The office underneath Mira</h1>
      <p className="max-w-2xl text-mute">
        Specialists are roles, not chatbots. They hand Mira typed results. Only Mira speaks to Elena.
        Deterministic engines sit below every agent — they do the arithmetic, matching, and risk scores.
        The runtime that would walk this graph is intentionally not built in this slice.
      </p>
      <OfficeGraph />
    </div>
  );
}
