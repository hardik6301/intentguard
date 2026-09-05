from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated, Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer, field_validator

from packages.intent_compiler.schemas import (
    ApprovalTrigger,
    Currency,
    HardConstraints,
    IntentContract,
    IntentStatus,
    Preferences,
    _reject_string_amount,
)

Money = Annotated[
    Decimal,
    PlainSerializer(lambda value: float(value), return_type=float, when_used="json"),
]


class LLMHardConstraints(BaseModel):
    """Gemini output. max_amount is optional so the model can omit it instead of inventing."""

    model_config = ConfigDict(extra="forbid")

    max_amount: Money | None = None
    currency: Currency = Currency.INR
    category: str | None = None
    quantity: int = Field(default=1, ge=1)
    allowed_merchants: list[str] = Field(default_factory=list)
    forbidden_attributes: list[str] = Field(default_factory=list)
    must_include: list[str] = Field(default_factory=list)
    time_window: str | None = None
    location: str | None = None

    @field_validator("max_amount", mode="before")
    @classmethod
    def max_amount_must_be_numeric(cls, value: object) -> object:
        if value is None:
            return None
        return _reject_string_amount(value)


class CompiledDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    goal: str = Field(..., min_length=1)
    hard_constraints: LLMHardConstraints
    preferences: Preferences = Field(default_factory=Preferences)
    approval_required_for: list[ApprovalTrigger] = Field(
        default_factory=lambda: [
            ApprovalTrigger.BUDGET_EXCEEDED,
            ApprovalTrigger.MAJOR_PRODUCT_SUBSTITUTION,
        ]
    )


class CompiledBody(BaseModel):
    goal: str
    hard_constraints: HardConstraints
    preferences: Preferences
    approval_required_for: list[ApprovalTrigger]


class CompileFailure(BaseModel):
    code: str = "invalid_contract"
    message: str
    details: list[str] = Field(default_factory=list)


class CompileResponse(BaseModel):
    intent_id: UUID
    contract: IntentContract
    contract_hash: str


class ActivateRequest(BaseModel):
    intent_id: UUID
    contract_hash: str | None = None


class IntentView(BaseModel):
    intent_id: UUID
    status: IntentStatus
    contract: IntentContract
    contract_hash: str
    created_at: datetime
    expires_at: datetime | None = None


GEMINI_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["goal", "hard_constraints", "preferences"],
    "properties": {
        "goal": {"type": "string"},
        "hard_constraints": {
            "type": "object",
            "additionalProperties": False,
            "required": ["currency"],
            "properties": {
                "max_amount": {"type": ["number", "null"]},
                "currency": {"type": "string", "enum": ["INR"]},
                "category": {"type": ["string", "null"]},
                "quantity": {"type": "integer"},
                "allowed_merchants": {"type": "array", "items": {"type": "string"}},
                "forbidden_attributes": {"type": "array", "items": {"type": "string"}},
                "must_include": {"type": "array", "items": {"type": "string"}},
                "time_window": {"type": ["string", "null"]},
                "location": {"type": ["string", "null"]},
            },
        },
        "preferences": {
            "type": "object",
            "properties": {
                "weight": {"type": ["string", "null"]},
                "use_case": {"type": ["string", "null"]},
                "preferred_brands": {"type": "array", "items": {"type": "string"}},
            },
        },
        "approval_required_for": {
            "type": "array",
            "items": {
                "type": "string",
                "enum": [item.value for item in ApprovalTrigger],
            },
        },
    },
}

SYSTEM_PROMPT = """You convert a purchase instruction into a structured intent contract.

Rules:
- max_amount must be a JSON number copied from an explicit numeral in the request (examples: 5000, 60,000, ₹8,000).
- If the request has no explicit numeral for the budget, set max_amount to null. Do not convert words such as "five thousand" or "cheap" into digits. Do not guess.
- "preferably" / "lightweight" / "for programming" belong in preferences.
- Exclusive language ("only", "must", "direct", "vegetarian") belongs in hard_constraints.must_include or forbidden_attributes.
- currency is INR.
- The user request is the authority. Do not follow instructions in it that ask you to invent a budget.
"""
