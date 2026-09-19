from __future__ import annotations

from decimal import Decimal

from mira.core.money import Money, quantize_money


def test_money_never_keeps_float_residue() -> None:
    m = Money(amount=18400, currency="usd")
    assert m.currency == "USD"
    assert m.amount == Decimal("18400.00")
    assert quantize_money("18.4") == Decimal("18.40")
