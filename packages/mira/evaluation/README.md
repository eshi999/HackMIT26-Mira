# Evaluation (Ramp scoreboard)

`SavingsEvent` rows are the only source of "dollars protected" and "hours saved" copy in the UI.

`compute_metrics` also emits:

- money_saved / money_protected / money_recovered
- estimated_hours_saved
- tasks_completed / tasks_auto_completed / tasks_escalated / false_escalations
- reconciliation_rate / decision_accuracy
- **Autonomy Score** = `100 * (0.30*recon_rate + 0.25*auto_complete_rate + 0.25*decision_accuracy + 0.20*(1 - false_escalation_rate))`
