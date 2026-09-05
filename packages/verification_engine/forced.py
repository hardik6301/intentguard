"""Eval-only semantic stand-in. Assessment only — no verdict."""

from packages.intent_compiler.schemas import IntentContract
from packages.verification_engine.schemas import (
    ProposedAction,
    SemanticAssessment,
    SubstitutionSeverity,
)


class ForcedLowSemanticVerifier:
    def verify(
        self,
        contract: IntentContract,
        proposal: ProposedAction,
        *,
        product_text: str | None = None,
    ) -> SemanticAssessment:
        del contract, proposal, product_text
        return SemanticAssessment(
            semantic_match=0.61,
            reason="Forced low confidence for failure injection.",
            substitution_severity=SubstitutionSeverity.MAJOR,
            error=False,
        )
