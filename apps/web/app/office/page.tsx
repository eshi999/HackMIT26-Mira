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
    <main className="mx-auto w-full max-w-[1400px] px-6 py-10 lg:px-8">
      <section className="max-w-4xl">
        <div className="inline-flex rounded-full border border-line px-3 py-1 text-[10px] uppercase tracking-[0.18em] text-ledger">
          How Mira works
        </div>

        <h1 className="mt-5 font-serif text-4xl leading-tight text-ivory lg:text-5xl">
          From signal to trusted finance action.
        </h1>

        <p className="mt-4 max-w-3xl text-base leading-7 text-mute">
          One AI CFO at the surface. A controlled finance operation underneath.
          Mira coordinates the work while deterministic systems remain the
          source of financial truth.
        </p>
      </section>

      <section className="mt-9 grid gap-3 md:grid-cols-2 xl:grid-cols-5">
        {steps.map((step, index) => (
          <article
            key={step.number}
            className="relative flex min-h-[230px] flex-col rounded-2xl border border-line bg-paper/55 p-5"
          >
            <div className="flex items-center justify-between">
              <span className="font-mono text-[10px] tracking-[0.18em] text-brass">
                {step.number}
              </span>

              {index < steps.length - 1 ? (
                <span
                  aria-hidden="true"
                  className="hidden text-line xl:block"
                >
                  →
                </span>
              ) : null}
            </div>

            <h2 className="mt-5 font-serif text-xl text-ivory">
              {step.title}
            </h2>

            <p className="mt-3 text-sm leading-6 text-mute">
              {step.description}
            </p>

            <p className="mt-auto border-t border-line pt-4 text-[11px] leading-5 text-mute">
              {step.detail}
            </p>
          </article>
        ))}
      </section>

      <section className="mt-5 grid gap-3 md:grid-cols-3">
        <div className="rounded-xl border border-line bg-paper/30 px-5 py-4">
          <p className="text-[10px] uppercase tracking-[0.16em] text-mute">
            Language
          </p>

          <p className="mt-2 text-sm text-ivory">
            The trained router understands what the executive is asking.
          </p>
        </div>

        <div className="rounded-xl border border-line bg-paper/30 px-5 py-4">
          <p className="text-[10px] uppercase tracking-[0.16em] text-mute">
            Financial truth
          </p>

          <p className="mt-2 text-sm text-ivory">
            Deterministic engines establish the numbers, controls, and evidence.
          </p>
        </div>

        <div className="rounded-xl border border-line bg-paper/30 px-5 py-4">
          <p className="text-[10px] uppercase tracking-[0.16em] text-mute">
            Authority
          </p>

          <p className="mt-2 text-sm text-ivory">
            Humans retain control over consequential financial decisions.
          </p>
        </div>
      </section>

      <footer className="mt-6 flex flex-wrap gap-x-5 gap-y-2 border-t border-line pt-5 text-xs text-mute">
        <span className="text-ledger">Mira coordinates.</span>
        <span>Deterministic systems verify.</span>
        <span>Humans retain control.</span>
      </footer>
    </main>
  );
}
