"""Deterministic string/amount helpers. No LLM."""

from __future__ import annotations

import re
from decimal import Decimal

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def normalize_reference(value: str | None) -> str:
    """Uppercase alphanumerics only. INV-10441, inv 10441, and 10441-A collapse predictably."""
    if not value:
        return ""
    return _NON_ALNUM.sub("", value.lower())


def levenshtein(left: str, right: str) -> int:
    if left == right:
        return 0
    if not left:
        return len(right)
    if not right:
        return len(left)
    prev = list(range(len(right) + 1))
    for i, char_l in enumerate(left, 1):
        curr = [i]
        for j, char_r in enumerate(right, 1):
            insert = curr[j - 1] + 1
            delete = prev[j] + 1
            substitute = prev[j - 1] + (char_l != char_r)
            curr.append(min(insert, delete, substitute))
        prev = curr
    return prev[-1]


def near_invoice_number(left: str, right: str, max_distance: int = 2) -> bool:
    a = normalize_reference(left)
    b = normalize_reference(right)
    if not a or not b:
        return False
    if a == b:
        return True
    if a in b or b in a:
        longer, shorter = (a, b) if len(a) >= len(b) else (b, a)
        if len(longer) - len(shorter) <= max_distance:
            return True
    return levenshtein(a, b) <= max_distance


def is_round_amount(amount: Decimal, min_amount: Decimal = Decimal("1000.00")) -> bool:
    """True when amount is a whole thousand (or larger round unit) with no cents."""
    if amount.copy_abs() < min_amount:
        return False
    if amount % Decimal("1.00") != 0:
        return False
    return amount % Decimal("1000.00") == 0


def period_from_date(value) -> str:
    return f"{value.year:04d}-{value.month:02d}"
