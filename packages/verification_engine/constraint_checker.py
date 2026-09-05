from __future__ import annotations

from datetime import datetime, time, timezone
from decimal import Decimal

from packages.intent_compiler.schemas import IntentContract
from packages.verification_engine.fingerprint import proposal_fingerprint
from packages.verification_engine.schemas import (
    HardConstraintFailure,
    HardConstraintResult,
    ProposedAction,
)


def check_constraints(
    contract: IntentContract,
    proposal: ProposedAction,
    *,
    now: datetime | None = None,
    existing_fingerprints: set[str] | None = None,
) -> HardConstraintResult:
    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)

    failures: list[HardConstraintFailure] = []
    hard = contract.hard_constraints

    if proposal.amount > hard.max_amount:
        failures.append(
            HardConstraintFailure(
                code="budget_exceeded",
                message=(
                    f"Proposed amount {_fmt_amount(proposal.amount)} exceeds maximum "
                    f"authorized {_fmt_amount(hard.max_amount)}."
                ),
            )
        )

    if proposal.currency.upper() != hard.currency.value:
        failures.append(
            HardConstraintFailure(
                code="currency_mismatch",
                message=f"Currency {proposal.currency} is not {hard.currency.value}.",
            )
        )

    quantity = _proposal_quantity(proposal)
    if quantity > hard.quantity:
        failures.append(
            HardConstraintFailure(
                code="quantity_exceeded",
                message=f"Quantity {quantity} exceeds authorized {hard.quantity}.",
            )
        )

    if hard.category and not _category_matches(hard.category, proposal.product.category):
        failures.append(
            HardConstraintFailure(
                code="category_mismatch",
                message=(
                    f"Category {proposal.product.category or 'missing'} does not match "
                    f"authorized {hard.category}."
                ),
            )
        )

    if hard.allowed_merchants:
        allowed = {item.casefold() for item in hard.allowed_merchants}
        if proposal.merchant.casefold() not in allowed:
            failures.append(
                HardConstraintFailure(
                    code="merchant_not_allowed",
                    message=f"Merchant {proposal.merchant} is not on the allowlist.",
                )
            )

    haystack = _haystack(proposal)
    for token in hard.forbidden_attributes:
        if token.casefold() in haystack:
            failures.append(
                HardConstraintFailure(
                    code="forbidden_attribute",
                    message=f"Proposal contains forbidden attribute '{token}'.",
                )
            )
    for token in hard.must_include:
        if token.casefold() not in haystack:
            failures.append(
                HardConstraintFailure(
                    code="missing_required_attribute",
                    message=f"Proposal is missing required constraint '{token}'.",
                )
            )

    if hard.location and not _location_matches(hard.location, proposal.location):
        failures.append(
            HardConstraintFailure(
                code="location_mismatch",
                message=f"Location {proposal.location or 'missing'} does not match {hard.location}.",
            )
        )

    window_failure = _time_window_failure(hard.time_window, proposal.scheduled_at)
    if window_failure:
        failures.append(window_failure)

    expires_at = contract.expires_at
    if expires_at is not None:
        expiry = expires_at if expires_at.tzinfo else expires_at.replace(tzinfo=timezone.utc)
        if moment > expiry:
            failures.append(
                HardConstraintFailure(
                    code="authorization_expired",
                    message="Authorization has expired.",
                )
            )

    if proposal.line_items:
        line_total = sum((item.amount * item.quantity for item in proposal.line_items), Decimal("0"))
        if line_total != proposal.amount:
            failures.append(
                HardConstraintFailure(
                    code="line_items_amount_mismatch",
                    message="Line item total does not match the proposed amount.",
                )
            )

    if existing_fingerprints is not None and contract.intent_id is not None:
        fingerprint = proposal_fingerprint(contract.intent_id, proposal)
        if fingerprint in existing_fingerprints:
            failures.append(
                HardConstraintFailure(
                    code="duplicate_transaction",
                    message="A proposal with this fingerprint was already submitted.",
                )
            )

    return HardConstraintResult(passed=not failures, failures=failures)


def _fmt_amount(value: Decimal) -> str:
    if value == value.to_integral_value():
        return str(int(value))
    return format(value, "f")


def _proposal_quantity(proposal: ProposedAction) -> int:
    if proposal.line_items:
        return sum(item.quantity for item in proposal.line_items)
    return proposal.quantity


def _category_matches(required: str, actual: str | None) -> bool:
    if not actual:
        return False
    want = required.casefold().strip()
    got = actual.casefold().strip()
    return want == got or want in got or got in want


def _location_matches(required: str, actual: str | None) -> bool:
    if not actual:
        return False
    want = required.casefold().strip()
    got = actual.casefold().strip()
    return want == got or want in got


def _haystack(proposal: ProposedAction) -> str:
    parts = [
        proposal.product.name,
        proposal.product.category or "",
        proposal.product.id,
        proposal.merchant,
        proposal.agent_rationale or "",
        " ".join(f"{key} {value}" for key, value in proposal.product.attributes.items()),
    ]
    for item in proposal.line_items:
        parts.append(item.name)
        parts.append(item.sku)
    return " ".join(parts).casefold()


def _time_window_failure(
    window: str | None,
    scheduled_at: datetime | None,
) -> HardConstraintFailure | None:
    if not window:
        return None
    if scheduled_at is None:
        return HardConstraintFailure(
            code="time_window_violation",
            message="Proposal is missing a scheduled time required by the contract.",
        )

    scheduled = scheduled_at if scheduled_at.tzinfo else scheduled_at.replace(tzinfo=timezone.utc)
    label = window.strip().casefold()
    hour = scheduled.hour

    bands = {
        "morning": (5, 12),
        "afternoon": (12, 17),
        "evening": (17, 21),
        "night": (21, 5),
    }
    for name, (start, end) in bands.items():
        if name in label:
            in_band = start <= hour < end if start < end else hour >= start or hour < end
            if not in_band:
                return HardConstraintFailure(
                    code="time_window_violation",
                    message=f"Scheduled time is outside the authorized {name} window.",
                )
            return None

    if "-" in window and "T" not in window:
        try:
            start_raw, end_raw = (part.strip() for part in window.split("-", 1))
            start = time.fromisoformat(start_raw)
            end = time.fromisoformat(end_raw)
            current = scheduled.timetz().replace(tzinfo=None)
            if not (start <= current <= end):
                return HardConstraintFailure(
                    code="time_window_violation",
                    message="Scheduled time is outside the authorized clock window.",
                )
            return None
        except ValueError:
            pass

    try:
        bound = datetime.fromisoformat(window.replace("Z", "+00:00"))
        if scheduled.date() != bound.date():
            return HardConstraintFailure(
                code="time_window_violation",
                message="Scheduled date does not match the authorized date.",
            )
    except ValueError:
        return HardConstraintFailure(
            code="time_window_violation",
            message="Authorization time window could not be evaluated.",
        )
    return None
