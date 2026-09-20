import { OfficeGraph } from "@/components/office-graph";
import { ContextEfficiency } from "@/components/context-efficiency";
import { Badge } from "@/components/ui/badge";

export default function OfficePage() {
  return (
    <div className="space-y-6">
      <Badge variant="ledger">One face to the company</Badge>
      <h1 className="font-serif text-4xl text-ivory">The office underneath Mira</h1>
      <p className="max-w-2xl text-mute">
        Specialists are roles, not chatbots. They hand Mira typed AgentTask results. Only Mira speaks to Elena.
        Deterministic engines sit below every agent — they do the arithmetic, matching, and risk scores.
        Mira plans, delegates, and reviews. The OpenAI Agents SDK is the planner; tools remain the source of financial truth.
      </p>
      <OfficeGraph />
      <ContextEfficiency />
    </div>
  );
}
