# Risk engine

`RiskAssessment.risk_score` and `FinancialIncident.risk_score` are produced here from explicit factors and `engine_version`.

Never let an LLM write `risk_score`.

**Risk** (how consequential) and **confidence** (how sure) are separate fields. They are never mixed into one number.

Detectors emit typed `Finding`s. Correlation groups them into `FinancialIncident`s with a scoring breakdown and an explanation derived from those factors.
