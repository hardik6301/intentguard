"""LLM semantic assessment. Must not emit a Verdict."""

from __future__ import annotations

import json
from typing import Protocol

from pydantic import ValidationError

from packages.intent_compiler.schemas import IntentContract
from packages.verification_engine.prompts import repair_prompt, verify_prompt
from packages.verification_engine.schemas import ProposedAction, SemanticAssessment
from packages.verification_engine.semantic_draft import SemanticDraft


class JsonModelClient(Protocol):
    def generate_json(self, prompt: str) -> str: ...


def _parse_draft(raw: str) -> tuple[SemanticDraft | None, list[str]]:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        return None, [f"invalid JSON: {exc.msg}"]
    if isinstance(payload, dict) and any(
        key in payload for key in ("verdict", "decision", "APPROVE", "PAUSE", "BLOCK")
    ):
        return None, ["semantic assessment must not include a verdict"]
    try:
        return SemanticDraft.model_validate(payload), []
    except ValidationError as exc:
        return None, [f"{'.'.join(str(part) for part in err['loc'])}: {err['msg']}" for err in exc.errors()]


def _fail_closed(reason: str) -> SemanticAssessment:
    return SemanticAssessment(
        semantic_match=None,
        violated_preferences=[],
        reason=reason,
        error=True,
    )


class SemanticVerifier:
    def __init__(self, llm: JsonModelClient) -> None:
        self.llm = llm

    def verify(
        self,
        contract: IntentContract,
        proposal: ProposedAction,
        *,
        product_text: str | None = None,
    ) -> SemanticAssessment:
        contract_json = contract.model_dump_json()
        proposal_json = proposal.model_dump_json()
        try:
            raw_output = self.llm.generate_json(
                verify_prompt(contract_json, proposal_json, product_text)
            )
            draft, errors = _parse_draft(raw_output)
            if errors:
                raw_output = self.llm.generate_json(
                    repair_prompt(contract_json, proposal_json, raw_output, errors, product_text)
                )
                draft, errors = _parse_draft(raw_output)
            if errors or draft is None:
                return _fail_closed("Semantic output invalid after retry.")
            return SemanticAssessment(
                semantic_match=draft.semantic_match,
                violated_preferences=draft.violated_preferences,
                substitution_severity=draft.substitution_severity,
                reason=draft.reason,
                error=False,
            )
        except TimeoutError:
            return _fail_closed("Semantic verifier timed out.")
        except Exception:
            return _fail_closed("Semantic verifier failed.")
