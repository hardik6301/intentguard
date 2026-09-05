from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator


class IntentStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    APPROVED = "approved"
    BLOCKED = "blocked"
    EXPIRED = "expired"
    PAID = "paid"


class Currency(str, Enum):
    INR = "INR"


class ApprovalTrigger(str, Enum):
    BUDGET_EXCEEDED = "budget_exceeded"
    MAJOR_PRODUCT_SUBSTITUTION = "major_product_substitution"
    BRAND_SUBSTITUTION = "brand_substitution"
    CONSTRAINT_AMBIGUITY = "constraint_ambiguity"


def _reject_string_amount(value: object) -> object:
    if isinstance(value, bool):
        raise ValueError("amount must be a number, not a boolean")
    if isinstance(value, str):
        raise ValueError("amount must be a number, not a string")
    return value


class HardConstraints(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_amount: Decimal = Field(..., gt=0, decimal_places=2, max_digits=12)
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
        return _reject_string_amount(value)

    @field_serializer("max_amount")
    def serialize_max_amount(self, value: Decimal) -> float:
        return float(value)


class DraftHardConstraints(BaseModel):
    """LLM-facing constraints. max_amount may be omitted; strings are still rejected."""

    model_config = ConfigDict(extra="forbid")

    max_amount: Decimal | None = Field(default=None, gt=0, decimal_places=2, max_digits=12)
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

    @field_serializer("max_amount")
    def serialize_max_amount(self, value: Decimal | None) -> float | None:
        return None if value is None else float(value)


class Preferences(BaseModel):
    model_config = ConfigDict(extra="allow")

    weight: str | None = None
    use_case: str | None = None
    preferred_brands: list[str] = Field(default_factory=list)


class IntentContract(BaseModel):
    """Immutable authorization object. max_amount is a number; strings are rejected."""

    model_config = ConfigDict(extra="forbid")

    intent_id: UUID | None = None
    created_at: datetime | None = None
    raw_request: str = Field(..., min_length=1)
    goal: str = Field(..., min_length=1)
    hard_constraints: HardConstraints
    preferences: Preferences = Field(default_factory=Preferences)
    approval_required_for: list[ApprovalTrigger] = Field(
        default_factory=lambda: [
            ApprovalTrigger.BUDGET_EXCEEDED,
            ApprovalTrigger.MAJOR_PRODUCT_SUBSTITUTION,
        ]
    )
    expires_at: datetime | None = None
    status: IntentStatus = IntentStatus.DRAFT


class CompiledDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    goal: str = Field(..., min_length=1)
    hard_constraints: DraftHardConstraints
    preferences: Preferences = Field(default_factory=Preferences)
    approval_required_for: list[ApprovalTrigger] = Field(
        default_factory=lambda: [
            ApprovalTrigger.BUDGET_EXCEEDED,
            ApprovalTrigger.MAJOR_PRODUCT_SUBSTITUTION,
        ]
    )


class CompileRequest(BaseModel):
    raw_request: str = Field(..., min_length=1)
    force_invalid_json: bool = False


class ActivateRequest(BaseModel):
    intent_id: UUID
    contract: IntentContract | None = None


class CompileError(BaseModel):
    code: str = "invalid_contract"
    message: str
    details: list[str] = Field(default_factory=list)


class CompileResponse(BaseModel):
    intent_id: UUID
    contract: IntentContract
    contract_hash: str


class IntentRecord(BaseModel):
    intent_id: UUID
    contract: IntentContract
    contract_hash: str
    status: IntentStatus


class CompileFailed(Exception):
    def __init__(
        self,
        message: str,
        details: list[str] | None = None,
        code: str = "invalid_contract",
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or []

    def to_model(self) -> CompileError:
        return CompileError(code=self.code, message=self.message, details=self.details)
