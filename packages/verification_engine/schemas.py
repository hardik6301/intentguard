from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

from packages.intent_compiler.schemas import _reject_string_amount


class ActionType(str, Enum):
    PURCHASE = "purchase"


class ProductRef(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    name: str
    category: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)


class LineItem(BaseModel):
    sku: str
    name: str
    amount: Decimal = Field(..., ge=0, decimal_places=2, max_digits=12)
    quantity: int = Field(default=1, ge=1)

    @field_validator("amount", mode="before")
    @classmethod
    def amount_must_be_numeric(cls, value: object) -> object:
        return _reject_string_amount(value)


class ProposedAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: ActionType = ActionType.PURCHASE
    amount: Decimal = Field(..., gt=0, decimal_places=2, max_digits=12)
    currency: str = "INR"
    merchant: str
    product: ProductRef
    quantity: int = Field(default=1, ge=1)
    line_items: list[LineItem] = Field(default_factory=list)
    agent_rationale: str | None = None
    scheduled_at: datetime | None = None
    location: str | None = None

    @field_validator("amount", mode="before")
    @classmethod
    def amount_must_be_numeric(cls, value: object) -> object:
        return _reject_string_amount(value)

    @field_serializer("amount")
    def serialize_amount(self, value: Decimal) -> float:
        return float(value)


class SubstitutionSeverity(str, Enum):
    NONE = "none"
    MINOR = "minor"
    MAJOR = "major"


class SemanticAssessment(BaseModel):
    """LLM output only. Never contains a payment decision."""

    model_config = ConfigDict(extra="forbid")

    semantic_match: float | None = Field(default=None, ge=0.0, le=1.0)
    violated_preferences: list[str] = Field(default_factory=list)
    substitution_severity: SubstitutionSeverity = SubstitutionSeverity.NONE
    reason: str = ""
    error: bool = False


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RiskAssessment(BaseModel):
    risk_level: RiskLevel = RiskLevel.LOW
    injection_high: bool = False
    flags: list[str] = Field(default_factory=list)


class HardConstraintFailure(BaseModel):
    code: str
    message: str


class HardConstraintResult(BaseModel):
    passed: bool
    failures: list[HardConstraintFailure] = Field(default_factory=list)


class Verdict(str, Enum):
    APPROVE = "APPROVE"
    PAUSE = "PAUSE"
    BLOCK = "BLOCK"


class Decision(BaseModel):
    """Written only by the deterministic decision engine."""

    verdict: Verdict
    reasons: list[str] = Field(default_factory=list)
    policy_version: str
    proposal_id: UUID | None = None
