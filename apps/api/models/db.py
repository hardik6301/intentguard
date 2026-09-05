from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    JSON,
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

JSONType = JSON().with_variant(JSONB(), "postgresql")


class Base(DeclarativeBase):
    pass


class IntentStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    APPROVED = "approved"
    BLOCKED = "blocked"
    EXPIRED = "expired"
    PAID = "paid"


class Verdict(str, Enum):
    APPROVE = "APPROVE"
    PAUSE = "PAUSE"
    BLOCK = "BLOCK"


class PaymentStatus(str, Enum):
    CREATED = "created"
    PENDING = "pending"
    UNKNOWN = "unknown"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    NOT_FOUND = "not_found"


class Intent(Base):
    __tablename__ = "intents"

    id: Mapped[Any] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    raw_request: Mapped[str] = mapped_column(Text, nullable=False)
    contract: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)
    contract_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=IntentStatus.DRAFT.value)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    proposals: Mapped[list["Proposal"]] = relationship(back_populates="intent")
    grants: Mapped[list["AuthorizationGrant"]] = relationship(back_populates="intent")


class Proposal(Base):
    __tablename__ = "proposals"

    id: Mapped[Any] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    intent_id: Mapped[Any] = mapped_column(Uuid(as_uuid=True), ForeignKey("intents.id"), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    intent: Mapped[Intent] = relationship(back_populates="proposals")
    verification: Mapped["Verification | None"] = relationship(back_populates="proposal")
    decision: Mapped["Decision | None"] = relationship(back_populates="proposal")
    grant: Mapped["AuthorizationGrant | None"] = relationship(back_populates="proposal")


class Verification(Base):
    __tablename__ = "verifications"

    id: Mapped[Any] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    proposal_id: Mapped[Any] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("proposals.id"), nullable=False, unique=True
    )
    hard_result: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)
    semantic_result: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)
    risk_result: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    proposal: Mapped[Proposal] = relationship(back_populates="verification")


class Decision(Base):
    __tablename__ = "decisions"

    id: Mapped[Any] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    proposal_id: Mapped[Any] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("proposals.id"), nullable=False, unique=True
    )
    verdict: Mapped[str] = mapped_column(String(16), nullable=False)
    reasons: Mapped[dict[str, Any] | list[Any]] = mapped_column(JSONType, nullable=False)
    policy_version: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    proposal: Mapped[Proposal] = relationship(back_populates="decision")


class AuthorizationGrant(Base):
    __tablename__ = "authorization_grants"

    id: Mapped[Any] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    intent_id: Mapped[Any] = mapped_column(Uuid(as_uuid=True), ForeignKey("intents.id"), nullable=False)
    proposal_id: Mapped[Any] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("proposals.id"), nullable=False, unique=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="INR")
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    intent: Mapped[Intent] = relationship(back_populates="grants")
    proposal: Mapped[Proposal] = relationship(back_populates="grant")
    payment: Mapped["Payment | None"] = relationship(back_populates="grant")


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_payments_idempotency_key"),
        UniqueConstraint("grant_id", name="uq_payments_grant_id"),
    )

    id: Mapped[Any] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    grant_id: Mapped[Any] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("authorization_grants.id"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=PaymentStatus.CREATED.value)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    grant: Mapped[AuthorizationGrant] = relationship(back_populates="payment")


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer(), "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    intent_id: Mapped[Any] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    actor: Mapped[str] = mapped_column(String(32), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)
