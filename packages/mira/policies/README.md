# Policies / controls

Evaluate `Policy.rules` JSON against a subject (invoice, PO). Emit violated policy IDs and whether Mira may act or must escalate.

Machine-evaluable examples:

- `POL-SPEND-CFO-10K` — purchases > $10,000 require CFO approval
- `POL-VENDOR-NEW-SECONDARY` — new vendors require secondary approval
- `POL-APPR-NO-SELF` — requester cannot approve own purchase
- `POL-PREC-AWS-12K` — AWS infrastructure below $12,000 may use an approved precedent
- `POL-CLOSED-PERIOD` — no posting to closed periods

Authority matrix belongs here, not in a prompt.
