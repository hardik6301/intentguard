from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

from packages.intent_compiler.schemas import HardConstraints, IntentContract
from packages.verification_engine.heuristic_semantic import HeuristicSemanticVerifier
from packages.verification_engine.schemas import ProductRef, ProposedAction, SemanticAssessment, SubstitutionSeverity
from packages.verification_engine.semantic_draft import SemanticDraft
from packages.verification_engine.semantic_verifier import SemanticVerifier


class ScriptedLLM:
    def __init__(self, responses: list[str] | Exception) -> None:
        self.responses = responses
        self.calls = 0

    def generate_json(self, prompt: str) -> str:
        self.calls += 1
        if isinstance(self.responses, Exception):
            raise self.responses
        if not self.responses:
            raise AssertionError("unexpected LLM call")
        return self.responses.pop(0)


def _contract(**overrides: object) -> IntentContract:
    now = datetime.now(timezone.utc)
    payload = {
        "intent_id": uuid4(),
        "raw_request": "Buy wireless headphones under 5000, preferably Sony or JBL",
        "goal": "Buy wireless headphones",
        "hard_constraints": HardConstraints(
            max_amount=Decimal("5000"),
            currency="INR",
            category="headphones",
        ),
        "created_at": now,
        "expires_at": now + timedelta(hours=1),
    }
    payload.update(overrides)
    return IntentContract.model_validate(payload)


def _proposal(**overrides: object) -> ProposedAction:
    payload = {
        "amount": 4500,
        "merchant": "demo_catalog",
        "product": ProductRef(id="sku_sony", name="Sony WH-1000XM5", category="headphones"),
    }
    payload.update(overrides)
    return ProposedAction.model_validate(payload)


def test_semantic_draft_schema_has_no_verdict() -> None:
    assert "verdict" not in SemanticDraft.model_fields
    dumped = SemanticDraft(semantic_match=0.9, reason="ok").model_dump()
    assert "verdict" not in dumped


def test_semantic_verifier_returns_assessment_not_decision() -> None:
    llm = ScriptedLLM(
        [
            '{"semantic_match": 0.88, "violated_preferences": [], "substitution_severity": "none", "reason": "Match."}'
        ]
    )
    result = SemanticVerifier(llm).verify(_contract(), _proposal())
    assert isinstance(result, SemanticAssessment)
    assert not hasattr(result, "verdict")


def test_valid_assessment_round_trip() -> None:
    llm = ScriptedLLM(
        [
            '{"semantic_match": 0.91, "violated_preferences": [], "substitution_severity": "none", "reason": "Same category and brand."}'
        ]
    )
    result = SemanticVerifier(llm).verify(_contract(), _proposal())
    assert result.error is False
    assert result.semantic_match == 0.91
    assert llm.calls == 1


def test_invalid_then_retry_then_fail_closed() -> None:
    llm = ScriptedLLM(["not-json", '{"semantic_match": "high"}'])
    result = SemanticVerifier(llm).verify(_contract(), _proposal())
    assert llm.calls == 2
    assert result.error is True
    assert result.semantic_match is None


def test_timeout_does_not_approve_signal() -> None:
    result = SemanticVerifier(ScriptedLLM(TimeoutError())).verify(_contract(), _proposal())
    assert result.error is True
    assert result.semantic_match is None


def test_verdict_in_model_output_is_rejected() -> None:
    llm = ScriptedLLM(
        [
            '{"semantic_match": 0.99, "reason": "ok", "verdict": "APPROVE"}',
            '{"semantic_match": 0.99, "decision": "APPROVE"}',
        ]
    )
    result = SemanticVerifier(llm).verify(_contract(), _proposal())
    assert result.error is True
    assert result.semantic_match is None


def test_heuristic_brand_substitution_is_pause_band() -> None:
    contract = _contract()
    contract.preferences.preferred_brands = ["Sony", "JBL"]
    result = HeuristicSemanticVerifier().verify(
        contract,
        _proposal(product=ProductRef(id="sku_bose", name="Bose QuietComfort", category="headphones")),
    )
    assert result.error is False
    assert result.semantic_match == 0.61
    assert result.substitution_severity is SubstitutionSeverity.MAJOR
