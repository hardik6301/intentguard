"""Local stand-in when GEMINI_API_KEY is unset. Assessment only — no verdict."""

from __future__ import annotations

from packages.intent_compiler.schemas import IntentContract
from packages.verification_engine.schemas import (
    ProposedAction,
    SemanticAssessment,
    SubstitutionSeverity,
)


class HeuristicSemanticVerifier:
    def verify(
        self,
        contract: IntentContract,
        proposal: ProposedAction,
        *,
        product_text: str | None = None,
    ) -> SemanticAssessment:
        haystack = _haystack(proposal, product_text)
        goal = " ".join(
            [
                contract.goal,
                contract.raw_request,
                contract.hard_constraints.category or "",
            ]
        ).casefold()
        violated: list[str] = []
        severity = SubstitutionSeverity.NONE
        score = 0.9
        reasons: list[str] = []

        for token in contract.hard_constraints.must_include:
            if token.casefold() not in haystack:
                score = min(score, 0.25)
                reasons.append(f"Missing required meaning '{token}'.")
                severity = SubstitutionSeverity.MAJOR

        for token in contract.hard_constraints.forbidden_attributes:
            if token.casefold() in haystack:
                score = min(score, 0.2)
                reasons.append(f"Proposal includes forbidden '{token}'.")
                severity = SubstitutionSeverity.MAJOR

        if "vegetarian" in goal and any(word in haystack for word in ("chicken", "non-vegetarian", "mutton")):
            score = min(score, 0.18)
            violated.append("vegetarian")
            severity = SubstitutionSeverity.MAJOR
            reasons.append("Proposed item conflicts with a vegetarian constraint.")

        brands = [brand for brand in contract.preferences.preferred_brands if brand.strip()]
        if brands:
            matched = any(brand.casefold() in haystack for brand in brands)
            if not matched:
                score = min(score, 0.61)
                violated.extend(brands)
                severity = SubstitutionSeverity.MAJOR
                reasons.append("Proposed brand is not among the preferred brands.")

        weight = (contract.preferences.weight or "").casefold()
        if "lightweight" in weight and any(word in haystack for word in ("gaming", "heavy", "chassis")):
            score = min(score, 0.61)
            violated.append("weight")
            if severity == SubstitutionSeverity.NONE:
                severity = SubstitutionSeverity.MAJOR
            reasons.append("Proposed product is a poor match for a lightweight preference.")

        required_category = (contract.hard_constraints.category or "").casefold()
        actual_category = (proposal.product.category or "").casefold()
        if required_category and actual_category and required_category not in actual_category and actual_category not in required_category:
            score = min(score, 0.35)
            severity = SubstitutionSeverity.MAJOR
            reasons.append("Proposed category does not match the authorized category.")

        if score >= 0.85 and not reasons:
            reasons.append("Proposed item matches the authorized goal and preferences.")

        return SemanticAssessment(
            semantic_match=score,
            violated_preferences=violated,
            substitution_severity=severity,
            reason=" ".join(reasons),
            error=False,
        )


def _haystack(proposal: ProposedAction, product_text: str | None) -> str:
    parts = [
        proposal.product.name,
        proposal.product.category or "",
        proposal.product.id,
        proposal.merchant,
        proposal.agent_rationale or "",
        product_text or "",
        " ".join(str(value) for value in proposal.product.attributes.values()),
    ]
    for item in proposal.line_items:
        parts.append(item.name)
        parts.append(item.sku)
    return " ".join(parts).casefold()
