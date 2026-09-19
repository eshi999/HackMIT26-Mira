# Agents

This package is a **protocol surface only** in the foundation slice.

- Typed I/O lives in `mira.core.agent_outputs`.
- Org roles live in `mira.agents.protocol.MIRA_ORG`.
- Mira is the only persona that speaks to the user (`speaks_to_user=True`).
- Do **not** add OpenAI Agents SDK loops here until `finance`, `risk`, `policies`, and `reconciliation` have tested engines.

Cognition/Devin: do not implement runtime in this folder without an explicit task.
