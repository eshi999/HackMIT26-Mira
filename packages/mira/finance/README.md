# Finance engine

Deterministic arithmetic only: money totals, aging, contract price ceilings, snapshot load.

LLMs may *read* outputs of this package. They may not add invoice lines or compound a contract increase.

- `snapshot.py` — frozen company picture for every engine
- `contracts.py` — `ContractFacts` vs invoice comparison
- `aging.py` — AR days overdue
- `normalize.py` — invoice-number and reference matching helpers
