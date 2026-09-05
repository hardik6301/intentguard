"""Injection and accessory-stuffing signals. Deterministic. No LLM."""

from __future__ import annotations

import re

from packages.verification_engine.schemas import ProposedAction, RiskAssessment, RiskLevel

INJECTION_PHRASES = (
    "ignore previous",
    "ignore all previous",
    "ignore instructions",
    "disregard previous",
    "disregard the contract",
    "forget the user",
    "new instructions",
    "system prompt",
    "proceed to payment",
    "you must pay",
    "override the contract",
    "budget is now",
    "authorized amount is",
    "add premium and pay",
    "jailbreak",
    "do not follow the user",
)

ACCESSORY_TOKENS = (
    "accessory",
    "accessories",
    "mouse",
    "warranty",
    "insurance",
    "extended protection",
    "gift card",
    "add-on",
    "addon",
    "premium bag",
    "sleeve",
)


def assess_risk(proposal: ProposedAction, *, product_text: str | None = None) -> RiskAssessment:
    haystack = _untrusted_text(proposal, product_text)
    flags: list[str] = []
    injection_high = any(phrase in haystack for phrase in INJECTION_PHRASES)
    if injection_high:
        flags.append("untrusted_instruction")
    if _accessory_stuffing(proposal, product_text):
        flags.append("accessory_stuffing")

    if injection_high or "accessory_stuffing" in flags:
        level = RiskLevel.HIGH
    elif flags:
        level = RiskLevel.MEDIUM
    else:
        level = RiskLevel.LOW

    return RiskAssessment(
        risk_level=level,
        injection_high=injection_high,
        flags=flags,
    )


def _untrusted_text(proposal: ProposedAction, product_text: str | None) -> str:
    parts = [
        proposal.product.name,
        proposal.product.category or "",
        proposal.product.id,
        proposal.agent_rationale or "",
        product_text or "",
        " ".join(str(value) for value in proposal.product.attributes.values()),
    ]
    for item in proposal.line_items:
        parts.append(item.name)
        parts.append(item.sku)
    return " ".join(parts).casefold()


def _accessory_stuffing(proposal: ProposedAction, product_text: str | None) -> bool:
    extra_skus = [
        item
        for item in proposal.line_items
        if item.sku.strip().casefold() != proposal.product.id.strip().casefold()
    ]
    if extra_skus:
        return True
    blob = " ".join(
        [item.name for item in proposal.line_items] + [product_text or ""]
    ).casefold()
    if not blob.strip():
        return False
    for token in ACCESSORY_TOKENS:
        if " " in token:
            if token in blob:
                return True
        elif re.search(rf"\b{re.escape(token)}\b", blob):
            return True
    return False
