from inspect import getsource
from uuid import uuid4

from packages.policy_engine.thresholds import POLICY_VERSION, SEMANTIC_BLOCK_BELOW
from packages.verification_engine import decision_engine
from packages.verification_engine.decision_engine import decide
from packages.verification_engine.schemas import (
    HardConstraintFailure,
    HardConstraintResult,
    RiskAssessment,
    RiskLevel,
    SemanticAssessment,
    SubstitutionSeverity,
    Verdict,
)


def _hard(passed: bool) -> HardConstraintResult:
    if passed:
        return HardConstraintResult(passed=True)
    return HardConstraintResult(
        passed=False,
        failures=[HardConstraintFailure(code="budget_exceeded", message="Budget exceeded.")],
    )


def _semantic(
    score: float | None,
    *,
    error: bool = False,
    severity: SubstitutionSeverity = SubstitutionSeverity.NONE,
) -> SemanticAssessment:
    return SemanticAssessment(
        semantic_match=score,
        substitution_severity=severity,
        reason="stub",
        error=error,
    )


def _risk(*, injection: bool = False, level: RiskLevel = RiskLevel.LOW) -> RiskAssessment:
    return RiskAssessment(
        risk_level=level,
        injection_high=injection,
        flags=["untrusted_instruction"] if injection else [],
    )


def test_decision_engine_does_not_import_llm() -> None:
    source = getsource(decision_engine)
    assert "gemini" not in source.lower()
    assert "genai" not in source.lower()
    assert "openai" not in source.lower()


def test_hard_fail_blocks_despite_high_semantic() -> None:
    result = decide(_hard(False), _semantic(0.99), _risk())
    assert result.verdict is Verdict.BLOCK
    assert result.policy_version == POLICY_VERSION


def test_semantic_0_61_pauses() -> None:
    result = decide(_hard(True), _semantic(0.61), _risk())
    assert result.verdict is Verdict.PAUSE


def test_semantic_error_does_not_approve() -> None:
    result = decide(_hard(True), _semantic(None, error=True), _risk())
    assert result.verdict is not Verdict.APPROVE
    assert result.verdict is Verdict.PAUSE


def test_missing_score_does_not_approve() -> None:
    result = decide(_hard(True), _semantic(None, error=False), _risk())
    assert result.verdict is not Verdict.APPROVE
    assert result.verdict is Verdict.PAUSE


def test_score_below_block_threshold_blocks() -> None:
    result = decide(_hard(True), _semantic(SEMANTIC_BLOCK_BELOW - 0.01), _risk())
    assert result.verdict is Verdict.BLOCK


def test_injection_high_blocks() -> None:
    result = decide(_hard(True), _semantic(0.99), _risk(injection=True, level=RiskLevel.HIGH))
    assert result.verdict is Verdict.BLOCK


def test_major_substitution_pauses_even_if_score_high() -> None:
    result = decide(
        _hard(True),
        _semantic(0.9, severity=SubstitutionSeverity.MAJOR),
        _risk(),
    )
    assert result.verdict is Verdict.PAUSE


def test_approve_when_hard_pass_high_semantic_low_risk() -> None:
    result = decide(_hard(True), _semantic(0.85), _risk(), proposal_id=uuid4())
    assert result.verdict is Verdict.APPROVE
    assert result.proposal_id is not None
