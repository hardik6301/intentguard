from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_serializer


class GrantView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    intent_id: UUID
    proposal_id: UUID
    amount: Decimal = Field(..., decimal_places=2, max_digits=12)
    currency: str
    expires_at: datetime
    used: bool
    token: str | None = None

    @field_serializer("amount")
    def serialize_amount(self, value: Decimal) -> float:
        return float(value)


class CheckoutSession(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key_id: str
    order_id: str
    amount_paise: int
    currency: str
    name: str = "IntentGuard"


class PaymentRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    grant_id: UUID
    intent_id: UUID | None = None
    provider: str
    provider_ref: str | None = None
    idempotency_key: str
    status: str
    amount: Decimal = Field(..., decimal_places=2, max_digits=12)
    currency: str = "INR"
    checkout: CheckoutSession | None = None

    @field_serializer("amount")
    def serialize_amount(self, value: Decimal) -> float:
        return float(value)


class SimulatedCharge(BaseModel):
    provider_ref: str
    idempotency_key: str
    amount: Decimal
    currency: str
    status: str
