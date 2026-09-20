"""Typed contractual facts. LLM extraction may populate later; comparison is code."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from mira.core.agent_outputs import Confidence, EvidenceReference
from mira.core.money import Money, quantize_money


class ContractFacts(BaseModel):
    """Extracted term sheet. Comparison code trusts these fields, not prose."""

    model_config = ConfigDict(frozen=True)

    agreed_price: Money
    allowed_annual_increase_pct: Decimal = Field(ge=0)
    payment_terms: str
    renewal_date: date | None = None
    termination_terms: str | None = None
    price_basis_date: date | None = None
    currency: str = "USD"

    @field_validator("allowed_annual_increase_pct", mode="before")
    @classmethod
    def _pct(cls, value: object) -> Decimal:
        return Decimal(str(value))


class ContractInvoiceComparison(BaseModel):
    model_config = ConfigDict(frozen=True)

    contract_id: UUID
    invoice_id: UUID
    expected_price: Money | None
    actual_price: Money
    increase_pct: Decimal | None
    allowed_increase_pct: Decimal | None
    years_elapsed: Decimal | None
    is_violation: bool | None
    is_complete: bool = True
    status: str = "pass"
    confidence: Confidence
    evidence: list[EvidenceReference] = Field(default_factory=list)
    explanation: str


def facts_from_extracted(extracted_terms: dict, *, fallback_price: Money | None = None) -> ContractFacts | None:
    """Map structured extracted_terms JSON onto ContractFacts. Not NLP.

    Never infer agreed_price from the invoice under test. `fallback_price` is
    rejected for that reason and ignored.
    """
    del fallback_price
    if not extracted_terms:
        return None
    price_raw = extracted_terms.get("agreed_price", extracted_terms.get("agreed_price_amount"))
    if price_raw is None:
        return None
    currency = str(extracted_terms.get("currency", "USD"))
    price = Money(amount=quantize_money(price_raw), currency=currency)
    increase = extracted_terms.get("allowed_annual_increase_pct", extracted_terms.get("allowed_annual_increase"))
    if increase is None:
        return None
    basis = extracted_terms.get("price_basis_date")
    renewal = extracted_terms.get("renewal_date")
    return ContractFacts(
        agreed_price=price,
        allowed_annual_increase_pct=Decimal(str(increase)),
        payment_terms=str(extracted_terms.get("payment_terms", "")),
        renewal_date=date.fromisoformat(renewal) if isinstance(renewal, str) else renewal,
        termination_terms=extracted_terms.get("termination_terms"),
        price_basis_date=date.fromisoformat(basis) if isinstance(basis, str) else basis,
        currency=price.currency,
    )


def expected_price_as_of(facts: ContractFacts, as_of: date) -> tuple[Money, Decimal]:
    """Compound the allowed increase by whole years since price_basis_date. Zero years if no basis."""
    basis = facts.price_basis_date
    years = Decimal("0")
    if basis is not None and as_of > basis:
        years = Decimal(str((as_of.year - basis.year) - (1 if (as_of.month, as_of.day) < (basis.month, basis.day) else 0)))
        if years < 0:
            years = Decimal("0")
    multiplier = (Decimal("1") + facts.allowed_annual_increase_pct / Decimal("100")) ** years
    expected = Money(
        amount=quantize_money(facts.agreed_price.amount * multiplier),
        currency=facts.agreed_price.currency,
    )
    return expected, years


def compare_invoice_to_contract(
    *,
    contract_id: UUID,
    invoice_id: UUID,
    facts: ContractFacts,
    invoice_amount: Money,
    invoice_date: date,
) -> ContractInvoiceComparison:
    expected, years = expected_price_as_of(facts, invoice_date)
    if expected.amount == 0:
        increase_pct = Decimal("0")
    else:
        increase_pct = quantize_money((invoice_amount.amount / facts.agreed_price.amount - 1) * Decimal("100"))
    allowed_after_years = quantize_money(
        ((expected.amount / facts.agreed_price.amount) - 1) * Decimal("100")
    ) if facts.agreed_price.amount else Decimal("0")
    # Violation: actual exceeds the allowed compounded ceiling.
    is_violation = invoice_amount.amount > expected.amount
    confidence = Confidence(
        score=Decimal("0.99"),
        basis="Contract agreed_price, allowed_annual_increase_pct, and invoice total are complete numeric fields.",
    )
    explanation = (
        f"Agreed price {facts.agreed_price.amount} with {facts.allowed_annual_increase_pct}% annual increase "
        f"over {years} year(s) allows {expected.amount}. Invoice is {invoice_amount.amount} "
        f"({increase_pct}% vs allowed {allowed_after_years}%). "
        + ("VIOLATION." if is_violation else "Within contract ceiling.")
    )
    evidence = [
        EvidenceReference(
            object_type="contract",
            object_id=contract_id,
            source_system="seed",
            locator="field:agreed_price",
            excerpt=str(facts.agreed_price.amount),
            role="policy_basis",
        ),
        EvidenceReference(
            object_type="invoice",
            object_id=invoice_id,
            source_system="seed",
            locator="field:total",
            excerpt=str(invoice_amount.amount),
            role="supporting",
        ),
    ]
    return ContractInvoiceComparison(
        contract_id=contract_id,
        invoice_id=invoice_id,
        expected_price=expected,
        actual_price=invoice_amount,
        increase_pct=increase_pct,
        allowed_increase_pct=facts.allowed_annual_increase_pct,
        years_elapsed=years,
        is_violation=is_violation,
        is_complete=True,
        status="violation" if is_violation else "pass",
        confidence=confidence,
        evidence=evidence,
        explanation=explanation,
    )
