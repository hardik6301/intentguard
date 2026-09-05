from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Protocol
from uuid import uuid4

from pydantic import ValidationError

from packages.intent_compiler.amounts import (
    MISSING_BUDGET_MESSAGE,
    UNGROUNDED_BUDGET_MESSAGE,
    resolve_max_amount,
)
from packages.intent_compiler.prompts import compile_prompt, repair_prompt
from packages.intent_compiler.schemas import (
    ApprovalTrigger,
    CompiledDraft,
    CompileFailed,
    HardConstraints,
    IntentContract,
    IntentStatus,
)


class JsonModelClient(Protocol):
    def generate_json(self, prompt: str) -> str: ...


def _apply_exclusive_language(raw_request: str, constraints: HardConstraints) -> HardConstraints:
    text = raw_request.lower()
    must = list(constraints.must_include)
    forbidden = list(constraints.forbidden_attributes)

    def add_must(token: str) -> None:
        if token not in must:
            must.append(token)

    def add_forbidden(token: str) -> None:
        if token not in forbidden:
            forbidden.append(token)

    if "vegetarian" in text or "veg only" in text:
        add_must("vegetarian")
        add_forbidden("non-vegetarian")
        add_forbidden("chicken")
    if "direct" in text and "flight" in text:
        add_must("direct")
        add_forbidden("layover")
        add_forbidden("one-stop")

    return constraints.model_copy(update={"must_include": must, "forbidden_attributes": forbidden})


def _validation_details(exc: ValidationError) -> list[str]:
    return [f"{'.'.join(str(part) for part in err['loc'])}: {err['msg']}" for err in exc.errors()]


def _parse_draft(raw: str) -> tuple[CompiledDraft | None, list[str]]:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        return None, [f"invalid JSON: {exc.msg}"]
    try:
        return CompiledDraft.model_validate(payload), []
    except ValidationError as exc:
        return None, _validation_details(exc)


class IntentCompiler:
    def __init__(self, llm: JsonModelClient, *, ttl_seconds: int = 3600) -> None:
        self.llm = llm
        self.ttl_seconds = ttl_seconds

    def compile(self, raw_request: str) -> IntentContract:
        text = raw_request.strip()
        if not text:
            raise CompileFailed(MISSING_BUDGET_MESSAGE, details=["raw_request is empty"])

        raw_output = self.llm.generate_json(compile_prompt(text))
        draft, errors = _parse_draft(raw_output)
        if errors:
            raw_output = self.llm.generate_json(repair_prompt(text, raw_output, errors))
            draft, errors = _parse_draft(raw_output)
            if errors or draft is None:
                raise CompileFailed(
                    MISSING_BUDGET_MESSAGE,
                    details=errors or ["structured output invalid after retry"],
                )
        assert draft is not None

        if draft.preferences.preferred_brands:
            triggers = list(draft.approval_required_for)
            if ApprovalTrigger.BRAND_SUBSTITUTION not in triggers:
                triggers.append(ApprovalTrigger.BRAND_SUBSTITUTION)
            draft = draft.model_copy(update={"approval_required_for": triggers})

        proposed = draft.hard_constraints.max_amount
        grounded = resolve_max_amount(text, proposed)
        if grounded is None:
            message = UNGROUNDED_BUDGET_MESSAGE if proposed is not None else MISSING_BUDGET_MESSAGE
            raise CompileFailed(message)

        hard = HardConstraints.model_validate(
            {
                **draft.hard_constraints.model_dump(),
                "max_amount": grounded,
            }
        )
        hard = _apply_exclusive_language(text, hard)

        now = datetime.now(timezone.utc)
        return IntentContract(
            intent_id=uuid4(),
            created_at=now,
            raw_request=text,
            goal=draft.goal,
            hard_constraints=hard,
            preferences=draft.preferences,
            approval_required_for=draft.approval_required_for,
            expires_at=now + timedelta(seconds=self.ttl_seconds),
            status=IntentStatus.DRAFT,
        )
