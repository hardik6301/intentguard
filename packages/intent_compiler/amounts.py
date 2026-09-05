from __future__ import annotations

import re
from decimal import Decimal

NUMBER = r"([0-9]{1,3}(?:,[0-9]{2,3})+|[0-9]+)(?:\.[0-9]+)?"
CURRENCY_MARK = r"(?:₹|rs\.?|inr)\s*"
BUDGET_CONTEXT = re.compile(
    rf"(?:under|below|upto|up\s*to|max(?:imum)?|budget(?:\s+of)?|less\s+than|"
    rf"within|no\s+more\s+than|not\s+more\s+than)\s*(?:{CURRENCY_MARK})?{NUMBER}",
    re.IGNORECASE,
)
CURRENCY_AMOUNT = re.compile(rf"{CURRENCY_MARK}{NUMBER}", re.IGNORECASE)

MISSING_BUDGET_MESSAGE = (
    "Enter a numeric budget. IntentGuard will not invent one."
)
UNGROUNDED_BUDGET_MESSAGE = (
    "Budget was not taken from an explicit numeral in your request. "
    + MISSING_BUDGET_MESSAGE
)


def parse_amount(raw: str) -> Decimal:
    return Decimal(raw.replace(",", ""))


def budget_candidates(text: str) -> list[Decimal]:
    found: list[Decimal] = []
    seen: set[Decimal] = set()

    def add(raw: str) -> None:
        amount = parse_amount(raw)
        if amount not in seen:
            seen.add(amount)
            found.append(amount)

    for match in BUDGET_CONTEXT.finditer(text):
        add(match.group(1))
    for match in CURRENCY_AMOUNT.finditer(text):
        add(match.group(1))
    return found


def amounts_equal(left: Decimal, right: Decimal) -> bool:
    return left == right


def resolve_max_amount(raw_request: str, proposed: Decimal | None) -> Decimal | None:
    """Return an amount only when it appears as an explicit numeral in the request."""
    candidates = budget_candidates(raw_request)
    if proposed is not None:
        for candidate in candidates:
            if amounts_equal(proposed, candidate):
                return proposed
        return None
    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) > 1:
        return max(candidates)
    return None
