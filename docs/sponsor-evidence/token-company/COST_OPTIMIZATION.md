# Measured context optimization

This implementation was written by **Codex**, not Devin. Token Company is **not live**
and is not integrated. No Token Company endpoint, SDK, credential scheme, compression
result, or sponsor attribution has been invented. All measurements below come from
Mira's offline context selection and structured packing.

Reproduce from the repository root:

```sh
make token-eval
```

The command seeds a fresh in-memory Northstar database, runs the same six requests in
both modes, and fails if serialized deterministic financial results, required facts,
or known unknowns differ. OFF includes the full structured snapshot and task tool
outputs. ON includes scoped context with a 6,000-token target; mandatory overflow is
reported and retained. This is a defined full-snapshot comparison, not a before/after
measurement of Mira's previous production prompts.

| Seeded scenario | Baseline items | Optimized items | Baseline bytes | Optimized bytes | Baseline estimated tokens | Optimized estimated tokens | Reduction |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| AP invoice review | 275 | 13 | 294,663 | 151,492 | 73,666 | 37,873 | 48.59% |
| AWS month-over-month investigation | 275 | 7 | 152,954 | 6,969 | 38,239 | 1,743 | 95.44% |
| Reconciliation | 275 | 121 | 243,432 | 150,936 | 60,858 | 37,734 | 38.00% |
| FP&A hiring | 275 | 27 | 158,487 | 23,814 | 39,622 | 5,954 | 84.97% |
| Audit | 275 | 22 | 384,331 | 243,801 | 96,083 | 60,951 | 36.56% |
| Executive cash/risk question | 275 | 10 | 294,302 | 148,872 | 73,576 | 37,218 | 49.42% |
| **Total** | **1,650** | **200** | **1,528,169** | **725,884** | **382,044** | **181,473** | **52.50%** |

**200,571 estimated input tokens avoided. Deterministic correctness retained in all
six scenarios; correctness delta zero.** Four scenarios exceed the target because
required reports and controls are never deleted. Figures are measured, not hardcoded
into the evaluator or UI. The API/UI reevaluates the current demo snapshot and may
show different context sizes after legitimate ledger/state changes.

Estimation is `ceil(UTF-8 bytes / 4)`, labeled `estimated`; it is not a provider token
count. It excludes system instructions, tool definitions/calls, and output tokens.
Provider-reported runtime counts, if available, are recorded separately. Pricing is
not configured: **no dollar savings are claimed**.

The single production integration hook adds budgeted context to the existing AWS
OpenAI Agents SDK investigation. OpenAI remains responsible for explanation and tool
selection; deterministic tools remain authoritative. Offline evaluation never calls
OpenAI, live Elasticsearch, Token Company, or other sponsor APIs. Elasticsearch uses
the existing local fallback; live-result ranking is covered with injected adapters.

See [implementation and limitations](../../CONTEXT_BUDGETER.md) for reproduction,
the pre-existing baseline SDK fake-runner test failure, and test coverage.

Validation: 156 Python tests passed, including 56 new tests; one pre-existing SDK
fake-runner test still fails (baseline: 100 passed, one failed). Ruff, TypeScript,
the production frontend build, paired token evaluation, and the existing finance
evaluation passed.
