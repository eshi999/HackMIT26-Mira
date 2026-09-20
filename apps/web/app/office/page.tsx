import { Card, CardContent } from "@/components/ui/card";

const steps = [
  {
    number: "01",
    title: "Observe",
    description:
      "Mira receives transactions, invoices, contracts, policies, and business signals.",
    detail: "Data · documents · events",
  },
  {
    number: "02",
    title: "Understand",
    description:
      "A trained intent model identifies the request and retrieves the relevant company context.",
    detail: "Intent · retrieval · context",
  },
  {
    number: "03",
    title: "Delegate",
    description:
      "Mira routes bounded work to the right finance capability instead of relying on one general chatbot.",
    detail: "AP/AR · Procurement · Treasury · FP&A · Control",
  },
  {
    number: "04",
    title: "Verify",
    description:
      "Deterministic systems calculate, match, check policy, score risk, and validate evidence.",
    detail: "Math · matching · policy · risk · evidence",
  },
  {
    number: "05",
    title: "Act or escalate",
    description:
      "Authorized low-risk work can proceed. High-risk or uncertain decisions stay with the human.",
    detail: "Automate where safe · review where needed",
  },
];

export default function OfficePage() {
  return (
    <div className="space-y-8">
      <section className="max-w-3xl">
        <h2 className="font-serif text-3xl leading-snug tracking-tight text-ivory">
          From signal to trusted finance action.
        </h2>
        <p className="mt-3 text-sm leading-6 text-mute">
          One AI CFO at the surface. A controlled finance operation underneath. Mira coordinates the
          work while deterministic systems remain the source of financial truth.
        </p>
      </section>

      <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
        {steps.map((step, index) => (
          <Card key={step.number} className="flex flex-col">
            <CardContent className="flex flex-1 flex-col pt-5">
              <div className="flex items-center justify-between">
                <span className="font-mono text-[10px] tracking-[0.18em] text-brass">{step.number}</span>
                {index < steps.length - 1 ? (
                  <span aria-hidden="true" className="hidden text-line xl:block">
                    →
                  </span>
                ) : null}
              </div>
              <h3 className="mt-5 font-serif text-xl text-ivory">{step.title}</h3>
              <p className="mt-3 text-sm leading-6 text-mute">{step.description}</p>
              <p className="mt-5 border-t border-line pt-4 text-xs leading-5 text-mute">{step.detail}</p>
            </CardContent>
          </Card>
        ))}
      </section>

      <section className="grid gap-3 md:grid-cols-3">
        <Card>
          <CardContent className="pt-5">
            <p className="text-xs text-mute">Language</p>
            <p className="mt-2 text-sm leading-6 text-ivory">
              The trained router understands what the executive is asking.
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-5">
            <p className="text-xs text-mute">Financial truth</p>
            <p className="mt-2 text-sm leading-6 text-ivory">
              Deterministic engines establish the numbers, controls, and evidence.
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-5">
            <p className="text-xs text-mute">Authority</p>
            <p className="mt-2 text-sm leading-6 text-ivory">
              Humans retain control over consequential financial decisions.
            </p>
          </CardContent>
        </Card>
      </section>

      <footer className="flex flex-wrap gap-x-5 gap-y-2 border-t border-line pt-5 text-xs text-mute">
        <span className="text-ledger">Mira coordinates.</span>
        <span>Deterministic systems verify.</span>
        <span>Humans retain control.</span>
      </footer>
    </div>
  );
}
