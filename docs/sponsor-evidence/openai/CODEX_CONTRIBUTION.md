# Codex contribution: deterministic snapshot isolation

## Defect discovered

During repository review, Codex identified two process-global dictionaries in
`packages/mira/agents/tools.py`: `_risk_cache` and `_recon_cache`. They stored
deterministic engine results under `id(snapshot)` without retaining the snapshot.
Python can reuse an object's ID after that object is destroyed, so a later
snapshot could inherit an earlier snapshot's financial results.

This affected the risk, reconciliation, and finance-metrics tools, as well as
invoice adjudication and command-center workflows that call those tools. The
financial engines themselves were not the source of this defect.

## Reproduction

Read-only review probes alternated fresh snapshots with and without findings or
reconciliation matches. When Python reused a snapshot ID, the tools returned the
earlier snapshot's result, including no risk findings for a snapshot that had
findings.

For repeatable regression coverage, Codex patched only the tools module's `id`
lookup to return the same value for distinct snapshots. This simulates ID reuse
without depending on allocator or garbage-collection timing and does not replace
Python's global built-in `id` function. Expected results come from direct calls
to the unchanged deterministic engines.

All six new regression cases failed against the original cache implementation.

## Change implemented

- Removed both process-global result caches.
- Changed `_cached_risk(snapshot)` to call `run_risk_engine(snapshot)` directly.
- Changed `_cached_recon(snapshot)` to call `reconcile(snapshot)` directly.
- Retained helper names/signatures for existing callers and preserved every
  public tool interface. The helper docstrings explain that they compute afresh.
- Added no replacement global cache.

The tradeoff is recomputation on each invocation in exchange for correct
snapshot isolation. Finance rules, risk rules, schemas, UI, integrations, and
OpenAI agent architecture were not changed. This contribution does not claim
that the product's OpenAI SDK orchestration was wired or executed.

## Regression tests

Added `packages/mira/tests/test_snapshot_isolation.py`, containing six collected
test cases:

1. `test_fresh_snapshots_do_not_share_risk`: an empty snapshot cannot suppress
   findings from a populated snapshot.
2. `test_fresh_snapshots_do_not_share_reconciliation`: an empty snapshot cannot
   suppress matches from a populated snapshot.
3. `test_alternating_fresh_snapshots_agree_with_direct_engine[risk]`: alternating
   populated/empty snapshots return the direct risk-engine result.
4. `test_alternating_fresh_snapshots_agree_with_direct_engine[reconciliation]`:
   alternating snapshots return the direct reconciliation-engine result.
5. `test_finance_metrics_use_current_snapshot_engine_results`: finance metrics
   agree with metrics calculated from direct engine results for each snapshot.
6. `test_repeated_workflows_agree_with_direct_engines_despite_reused_identity`:
   repeated invoice/briefing operations match an uncached reference sequence
   starting from the same database state, despite a preceding empty snapshot
   and forced identity collisions. The comparison includes persisted decision
   payload/status and briefing financial outputs, excluding generated workflow
   identities and timestamps.

## Validation

Full Python suite:

```text
.venv/bin/python -m pytest -q
66 passed in 11.85s
```

The previous suite contained 60 tests; this contribution adds six regression
cases. Ruff checks passed for both changed Python files, and `git diff --check`
passed.

## Files changed

- `packages/mira/agents/tools.py`
- `packages/mira/tests/test_snapshot_isolation.py`
- `docs/sponsor-evidence/openai/CODEX_CONTRIBUTION.md`

The pre-existing local change to `apps/api/app/routers/meta.py` was left untouched.
