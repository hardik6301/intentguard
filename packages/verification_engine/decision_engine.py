"""Pure decision function. No LLM. Thresholds live in policy_engine."""

from __future__ import annotations

from uuid import UUID

from packages.policy_engine.thresholds import (
    POLICY_VERSION,
    SEMANTIC_APPROVE_AT_OR_ABOVE,
    SEMANTIC_BLOCK_BELOW,
)
from packages.verification_engine.schemas import (
    Decision,
    HardConstraintResult,
    RiskAssessment,
    RiskLevel,
    SemanticAssessment,
    SubstitutionSeverity,
    Verdict,
)


def decide(
    hard: HardConstraintResult,
    semantic: SemanticAssessment,
    risk: RiskAssessment,
    *,
    proposal_id: UUID | None = None,
) -> Decision:
    if not hard.passed:
        reasons = [item.message for item in hard.failures] or ["Hard constraints failed."]
        return _decision(Verdict.BLOCK, reasons, proposal_id)

    if risk.injection_high:
        return _decision(
            Verdict.BLOCK,
            ["Untrusted instruction detected in proposal content."],
            proposal_id,
        )

    if risk.risk_level == RiskLevel.HIGH:
        flags = risk.flags or ["high_risk"]
        return _decision(
            Verdict.BLOCK,
            [f"Risk is high ({', '.join(flags)})."],
            proposal_id,
        )

    if semantic.error or semantic.semantic_match is None:
        return _decision(
            Verdict.PAUSE,
            ["Semantic verification did not complete. Approval requires a valid score."],
            proposal_id,
        )

    score = semantic.semantic_match
    if score < SEMANTIC_BLOCK_BELOW:
        return _decision(
            Verdict.BLOCK,
            [f"Semantic match {score:.0%} is below the block threshold."],
            proposal_id,
        )

    major = semantic.substitution_severity == SubstitutionSeverity.MAJOR
    if score < SEMANTIC_APPROVE_AT_OR_ABOVE or major:
        reasons: list[str] = []
        if score < SEMANTIC_APPROVE_AT_OR_ABOVE:
            reasons.append(f"Semantic match {score:.0%} requires review.")
        if major:
            reasons.append("Major substitution relative to the authorized intent.")
        if semantic.reason:
            reasons.append(semantic.reason)
        return _decision(Verdict.PAUSE, reasons, proposal_id)

    if risk.risk_level == RiskLevel.MEDIUM:
        return _decision(
            Verdict.PAUSE,
            ["Risk is medium. Approval requires low risk."],
            proposal_id,
        )

    return _decision(
        Verdict.APPROVE,
        ["Hard constraints passed, semantic match is high, and risk is low."],
        proposal_id,
    )


def _decision(verdict: Verdict, reasons: list[str], proposal_id: UUID | None) -> Decision:
    return Decision(
        verdict=verdict,
        reasons=reasons,
        policy_version=POLICY_VERSION,
        proposal_id=proposal_id,
    )
