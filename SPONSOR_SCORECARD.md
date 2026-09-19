# HackMIT 2026 Sponsor Scorecard

Mira's job is to satisfy these challenges **in the product**, not in a slide. This scorecard is the contract: what we will prove, how a judge will see it, and what is in this foundation slice versus later hours.

Legend: **Foundation** = shipped in this PR · **Planned** = designed, not yet implemented · **Demo-critical** = must work live on judging day.

---

## 1. Maximor — Agentic Office of the CFO

**Ask:** An agentic system that runs the Office of the CFO: multi-agent collaboration, shared company context, handoffs, memory across periods, self-improvement from feedback, long-horizon workflows, auditable decisions, human review when uncertain.

**How Mira answers:** One employee (Mira) plans work as an `AgentRun`, delegates typed `AgentTask`s to specialist roles (AP, Treasury, Procurement, Audit, FP&A), reviews `AgentTaskResult`s, writes a `Decision` with evidence/confidence/risk/authority, and opens an `Approval` when policy or confidence requires a human. `Precedent` is how the office remembers a period from the last one.

**Exact planned proof (judges see):**
1. Command center shows Mira — not six chat windows — with specialist work visible as an org/task graph (`/office`).
2. A multi-step AP close: ingest → duplicate catch → policy → decision → human exception.
3. A precedent from a prior period changing a current recommendation ("we reject rush SaaS without VP IT").
4. Audit trail: every write is an `AuditEvent`; a decision packet lists evidence.
5. A low-confidence GPU purchase stops for Elena Voss.

**This PR:** Canonical `AgentRun` / `AgentTask` / `Decision` / `Approval` / `Precedent` / `AuditEvent` models, typed I/O schemas, Northstar seed with one awaiting-human decision. **No agent runtime yet.**

**Demo-critical:** Yes, after slice 4.

---

## 2. Long Lake — Convince an AI non-believer

**Ask:** Transform messy finance operations into measurable value quickly, for a skeptic.

**How Mira answers:** Northstar Labs starts as a Dropbox-shaped pile (invoices, a duplicate, a stale PO, a contract, a policy PDF). Within one briefing Mira shows: dollars blocked, hours returned, the one action that still needs a human, and the evidence. No prompt engineering theater.

**Exact planned proof:**
1. Before: folder of badly named files + an overdue vendor.
2. After (same session): "I blocked $18,400 in duplicate HelixCloud AP. I need you on a $67,000 GPU buy. Estimated 6.5 controller hours returned this week."
3. Skeptic can open the duplicate packet and see both invoices, the match rule, and the policy — not a vibes score.

**This PR:** Seeded messy inbox, duplicate finding, savings events, command-center briefing UI.

**Demo-critical:** Yes. This is the opening 90 seconds.

---

## 3. ASUS — Hardware and/or Zenni Claw

**Ask:** Use ASUS hardware and/or Zenni Claw. Prefer both. Mira should become a custom Zenni Claw CFO skill.

**How Mira answers:** Finance workflows are exposed as a **safe skill API** (`/api/v1/skills/cfo/*`): briefing, cash, invoice intake, procurement, decision resolve. Zenni Claw invokes Mira the same way the UI and Deepgram do. Designed to run on an ASUS box as the local/edge client that talks to the skill routes.

**Exact planned proof:**
1. Documented skill contract in this repo (`packages/mira/integrations/zenni.py`).
2. Live: a Claw utterance or skill trigger returns Northstar's briefing JSON and can queue a procurement **without** opening the web chatbot.
3. If hardware is on-site: run the skill against a laptop/ASUS device hitting the same API.

**This PR:** Adapter interface, route namespace reserved in architecture, token/authority notes. **No Claw runtime wiring yet.**

**Assumptions requiring sponsor docs:**
- Zenni Claw custom skill auth model (token, device identity, allowlist).
- Whether Claw must call a public HTTPS URL vs localhost.
- ASUS device availability at judging and any required SDK.

**Demo-critical:** Skill API must work; physical Claw is best-effort if hardware is provided.

---

## 4. Visa — Reimagine commerce with generative AI

**Ask:** Natural-language need → budget check → policy check → product/vendor decision → approval → purchase/sandbox payment → invoice → reconciliation.

**How Mira answers:** The procurement vertical is a single `AgentRun` of type `procurement`. Mira parses the need, finance engines check budget and policy, procurement proposes a vendor, an `Approval` is created if required, a **Visa sandbox** `Payment` (`is_sandbox=true`) is recorded, an `Invoice` is filed, reconciliation matches PO ↔ receipt ↔ invoice ↔ payment.

**Exact planned proof:**
1. Need: "We need two inference GPUs for the Q4 eval cluster, under the lab capex policy."
2. Screen shows budget remaining, policy (dual approval > $10k), vendor choice, confidence, evidence.
3. Elena approves. Sandbox payment posts with a visible **SANDBOX** badge.
4. Invoice + reconciliation case close. Savings/hours recorded.

**This PR:** `PurchaseOrder`, `GoodsReceipt`, `Invoice`, `Payment`, `Budget`, `Approval` models; seeded GPU procurement awaiting approval. **No execution engine yet.**

**Assumptions requiring sponsor docs:**
- Visa sandbox credentials, merchant test cards, and whether a hosted checkout is required vs a recorded sandbox payment intent.
- Branding rules for "sandbox / simulated".

**Demo-critical:** Yes, as a traced happy path. Real network settlement is not required if sandbox labeling is honest.

---

## 5. Voloridge — Real-world public data

**Ask:** Use public/economic datasets to enrich finance analysis and identify signals.

**How Mira answers:** `ExternalSignal` stores public series (e.g. 3-month Treasury yield, CPI) with source, as-of date, and a pointer into the decision they influenced. Treasury/FP&A uses them as **context for cash placement**, not as generated opinions. Demo fixtures ship; a FRED adapter can replace them.

**Exact planned proof:**
1. Command center "Signals" rail: 3-month T-bill vs Northstar operating cash.
2. A recommendation: "Yield on idle cash is 4.x% public; we are earning ~0 on the operating account — flag for Elena." Evidence links the series id and as-of date.
3. Source citation is visible (FRED or seeded public snapshot).

**This PR:** `ExternalSignal` model + seeded series on Northstar.

**Assumptions requiring sponsor docs:**
- Preferred series / licensed datasets Voloridge wants highlighted.
- Any attribution language.

**Demo-critical:** Signal on the briefing is enough; live FRED fetch is optional.

---

## 6. Ramp — Save time and save money

**Ask:** Every workflow tracks measurable dollars protected/saved and estimated human hours saved.

**How Mira answers:** `SavingsEvent` is written by workflow code (never by an LLM). Categories: duplicate prevented, policy block, early-pay discount, hours of intake/coding avoided. The command center totals MTD dollars and hours. `packages/mira/evaluation` will own the metric definitions so we cannot invent a number in copy.

**Exact planned proof:**
1. Northstar MTD: dollars protected and hours saved on the home briefing.
2. Click-through to the HelixCloud duplicate: $18,400 protected, 1.5 AP hours.
3. Evaluation tests: given a duplicate match, the savings event math is exact.

**This PR:** `SavingsEvent` + `Metric` models, seeded totals, briefing API fields.

**Demo-critical:** Yes. Numbers must come from rows, not from UI copy.

---

## 7. Dropbox — Turn digital chaos into something useful

**Ask:** Ingest a messy finance document repository (invoices, receipts, contracts, statements, policies).

**How Mira answers:** `Document` + storage adapter. Default: `data/demo/inbox` with deliberately ugly filenames. Live: Dropbox folder watch/list. Classification and extraction feed canonical objects; originals remain evidence.

**Exact planned proof:**
1. Show the inbox dump (mixed types, bad names).
2. Show the same files as `Document` rows with class (`invoice`, `policy`, `contract`, `statement`).
3. Open one invoice whose `EvidenceReference` points at the file locator.

**This PR:** Local inbox files, `Document` model, storage adapter interface.

**Assumptions requiring sponsor docs:**
- Dropbox app permissions (files.content.read), sample folder, and whether a refresh-token flow is expected on the judging network.

**Demo-critical:** Local inbox is the guarantee; Dropbox live is the flourish.

---

## 8. Elastic — Find the signal

**Ask:** Searchable evidence layer across transactions, documents, decisions, anomalies.

**How Mira answers:** `packages/mira/evidence` projects those objects into an Elastic index (`mira-evidence`). The `/evidence` page is the human UI. When Elastic is down, SQL search still returns Northstar evidence so the demo does not die.

**Exact planned proof:**
1. Query "HelixCloud duplicate" returns the two invoices, the finding, the decision, and the policy clause.
2. Query "anomaly" / "overdue" returns Apex Scientific.
3. Index mapping documented; one integration test against Elastic when the `search` Compose profile is up.

**This PR:** Evidence models + adapter stub. **No Elastic client calls yet.**

**Assumptions requiring sponsor docs:**
- Preferred Elastic Cloud vs local 8.x, auth, and any required use of specific Elastic features (ELSER, etc.).

**Demo-critical:** Search UI must work (SQL fallback acceptable; Elastic is the sponsor proof).

---

## 9. Arrowstreet — Textual analysis

**Ask:** Serious textual analysis across contracts, policies, invoices, and financial documents.

**How Mira answers:** Extraction into **schemas** (contract term sheet, policy rules, invoice header/lines), plus findings: non-standard liability, auto-renewal, conflicting spend policy vs contract cap. Analysis writes `Finding` + `EvidenceReference` locators (page/clause), not a chat summary. Deterministic checks (amounts, dates, vendor names) still belong to engines.

**Exact planned proof:**
1. HelixCloud MSA: extracted term (auto-renew, liability cap) vs invoice in force.
2. Spend policy v3 vs GPU PO: dual-approval clause cited by locator.
3. A side-by-side: clause text, structured field, why it mattered to a decision.

**This PR:** `Contract`, `Policy`, `Document`, `Finding` models; seeded policy/contract text. **No NLP pipeline yet.**

**Demo-critical:** At least one contract and one policy must drive a visible decision packet.

---

## 10. OpenAI — The Fifth Teammate

**Ask:** Agent/tool orchestration as a real operating member of the finance org, not only text generation.

**How Mira answers:** OpenAI Agents SDK runs **inside** `packages/mira/agents` as Mira + specialists. Tools are the deterministic engines and DB writes. The model never adds two numbers. Structured outputs are the Pydantic types in `agent_outputs.py`. Mira is on the org chart as an employee with a queue, not a playground.

**Exact planned proof:**
1. An `AgentRun` trace in `/office`: Mira → AP specialist → policy engine → Mira review → Decision.
2. Tool calls visible: `detect_duplicates`, `score_risk`, `evaluate_policy` — not "write me a memo".
3. A forced failure: if confidence < threshold, Mira uses `HumanEscalation` instead of acting.

**This PR:** Typed outputs + `AgentRole` + protocol module. **STOP — no SDK runtime.**

**Assumptions requiring sponsor docs:**
- Allowed models, rate limits, and whether Agents SDK (vs Responses + tools) is the required surface.

**Demo-critical:** Yes, after engines exist. Do not demo a raw chat completion.

---

## 11. Deepgram — Voice interface for an executive

**Ask:** An executive can talk to Mira and trigger **safe** actions.

**How Mira answers:** Deepgram transcribes into the same skill API as Zenni. Voice can request a briefing or queue procurement. Spend requires a confirmation phrase and still honors `requires_human_approval`. Mira answers with a spoken briefing, not an open chat.

**Exact planned proof:**
1. "Mira, what did you catch overnight?" → spoken/on-screen briefing.
2. "Start procurement for two eval GPUs." → same procurement run as the UI.
3. "Pay the Apex invoice." → refused or escalated; not silent execution.

**This PR:** Deepgram adapter stub; voice uses the future skill routes.

**Assumptions requiring sponsor docs:**
- Streaming vs pre-recorded file, API key scope, and browser mic constraints on the judging network.

**Demo-critical:** One briefing-by-voice path. Action-by-voice is gated.

---

## 12. Cognition — Meaningful work for Devin

**Ask:** Architecture modular enough that independent verticals can be assigned cleanly.

**How Mira answers:** Each engine is a package with a README, typed interfaces, and tests. Canonical objects live only in `mira.core`. This scorecard is the assignment sheet.

**Exact planned proof:**
1. This repository layout.
2. At least one vertical (engines) implemented/tested by Devin without rewriting Invoice.
3. Boot tests that fail if a vertical breaks the import surface.

**This PR:** Package layout, READMEs, boot tests, assignment cuts in `ARCHITECTURE.md`.

**Demo-critical:** Process, not a stage demo — but the modularity must be real.

---

## 13. Cursor / SpaceXAI — Clean, ambitious, polished

**Ask:** Built with Cursor + Grok; architecture should be clean and demo-ready.

**How Mira answers:** This foundation is a Grok/Cursor cloud-agent slice: docs, models, API, command-center UI, seed, tests. Later slices stay on the same branch discipline (`cursor/…-6c90`).

**Exact planned proof:**
1. `ARCHITECTURE.md` / `DATA_MODEL.md` / this scorecard in the repo.
2. `make test` and `make typecheck` green.
3. Homepage is a CFO command center, not a chatbot.

**This PR:** The proof.

**Demo-critical:** Yes — polish of the command center is the first impression.

---

## Priority if time collapses

Never sacrifice the core demo to add another integration.

1. Long Lake briefing on Northstar (command center + duplicate + human gate)
2. Maximor auditability (Decision + evidence + approval)
3. Ramp numbers from `SavingsEvent` rows
4. Visa sandbox procurement path
5. Dropbox inbox (local is enough)
6. Elastic search
7. Arrowstreet clause extraction
8. Voloridge signal on the rail
9. OpenAI agent runtime (after engines)
10. Deepgram briefing
11. Zenni skill on the same API
12. Cognition vertical handoff (already enabled)
13. Cursor polish pass

---

## Foundation coverage matrix

| Sponsor | Models / docs | Seed | UI | Engine | Agent | Live adapter |
| --- | --- | --- | --- | --- | --- | --- |
| Maximor | yes | partial | shell | **risk/policy/recon** | — | — |
| Long Lake | yes | yes | briefing | **duplicate + savings math** | — | — |
| ASUS / Zenni | contract | — | — | — | — | stub |
| Visa | yes | PO/approval | card | **3-way + policy** | — | stub |
| Voloridge | yes | signals | rail | **observation≠interpretation** | — | demo + Treasury API |
| Ramp | yes | savings | totals | **metrics + autonomy score** | — | n/a |
| Dropbox | yes | inbox files | evidence list | — | — | stub |
| Elastic | yes | evidence rows | page shell | **index docs + source_id** | — | demo projection |
| Arrowstreet | yes | policy/contract | — | **contract facts vs invoice** | — | — |
| OpenAI | schemas | — | office graph | engines ready as tools | STOP | — |
| Deepgram | stub | — | — | — | — | stub |
| Cognition | packages | — | — | **engines tested** | — | n/a |
| Cursor | this repo | yes | yes | **this phase** | — | n/a |
