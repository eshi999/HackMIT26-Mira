"""Decimal money. LLMs never compute this; engines and models do."""

from __future__ import annotations

from decimal import ROUND_HALF_EVEN, Decimal
from typing import Any

from pydantic import BaseModel, field_validator

TWOPLACES = Decimal("0.01")


def quantize_money(value: Decimal | int | str | float) -> Decimal:
    if isinstance(value, float):
        # Accept JSON numbers but immediately freeze to Decimal via string
        # to avoid binary float residue. Callers should prefer str/Decimal.
        value = format(value, "f")
    return Decimal(value).quantize(TWOPLACES, rounding=ROUND_HALF_EVEN)


class Money(BaseModel):
    amount: Decimal
    currency: str = "USD"

    @field_validator("amount", mode="before")
    @classmethod
    def _quantize(cls, v: Any) -> Decimal:
        return quantize_money(v)

    @field_validator("currency")
    @classmethod
    def _upper(cls, v: str) -> str:
        code = v.strip().upper()
        if len(code) != 3:
            raise ValueError("currency must be ISO 4217 (3 letters)")
        return code

    def __add__(self, other: Money) -> Money:
        if self.currency != other.currency:
            raise ValueError("cannot add mixed currencies")
        return Money(amount=self.amount + other.amount, currency=self.currency)

    def __sub__(self, other: Money) -> Money:
        if self.currency != other.currency:
            raise ValueError("cannot subtract mixed currencies")
        return Money(amount=self.amount - other.amount, currency=self.currency)
