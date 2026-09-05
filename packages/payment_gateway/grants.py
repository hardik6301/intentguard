"""Single-use authorization grants. HMAC token is reconstructable until used."""

from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from apps.api.models.db import AuthorizationGrant
from packages.payment_gateway.errors import GrantInvalid, GrantMismatch, GrantRequired
from packages.payment_gateway.schemas import GrantView


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _payload(grant: AuthorizationGrant) -> str:
    expires = grant.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    expires = expires.astimezone(timezone.utc).replace(microsecond=0)
    amount = Decimal(grant.amount).quantize(Decimal("0.01"))
    return (
        f"{grant.id}|{grant.intent_id}|{grant.proposal_id}|{amount:.2f}|"
        f"{grant.currency}|{expires.strftime('%Y-%m-%dT%H:%M:%SZ')}"
    )


def issue_token(grant: AuthorizationGrant, secret: str) -> str:
    signature = hmac.new(secret.encode("utf-8"), _payload(grant).encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{grant.id}.{signature}"


def mint_grant(
    db: Session,
    *,
    intent_id: UUID,
    proposal_id: UUID,
    amount: Decimal,
    currency: str,
    ttl_seconds: int,
    secret: str,
    now: datetime | None = None,
) -> tuple[AuthorizationGrant, str]:
    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    grant = AuthorizationGrant(
        id=uuid4(),
        intent_id=intent_id,
        proposal_id=proposal_id,
        token_hash="pending",
        amount=Decimal(amount).quantize(Decimal("0.01")),
        currency=currency,
        expires_at=(moment + timedelta(seconds=ttl_seconds)).replace(microsecond=0),
    )
    token = issue_token(grant, secret)
    grant.token_hash = _digest(token)
    db.add(grant)
    return grant, token


def to_view(grant: AuthorizationGrant, secret: str, *, include_token: bool) -> GrantView:
    used = grant.used_at is not None
    return GrantView(
        id=grant.id,
        intent_id=grant.intent_id,
        proposal_id=grant.proposal_id,
        amount=Decimal(grant.amount),
        currency=grant.currency,
        expires_at=grant.expires_at,
        used=used,
        token=None if used or not include_token else issue_token(grant, secret),
    )


def authenticate_grant(
    db: Session,
    *,
    token: str,
    amount: Decimal,
    currency: str,
    secret: str,
    now: datetime | None = None,
    require_unused: bool = True,
) -> AuthorizationGrant:
    if not token or "." not in token:
        raise GrantRequired()
    grant_id_raw, _, _signature = token.partition(".")
    try:
        grant_id = UUID(grant_id_raw)
    except ValueError as exc:
        raise GrantInvalid() from exc
    grant = db.get(AuthorizationGrant, grant_id)
    if grant is None:
        raise GrantInvalid()
    expected = issue_token(grant, secret)
    if not hmac.compare_digest(token, expected) or _digest(token) != grant.token_hash:
        raise GrantInvalid()
    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    expires = grant.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if moment > expires:
        raise GrantInvalid("Authorization grant has expired")
    if Decimal(grant.amount).quantize(Decimal("0.01")) != Decimal(amount).quantize(Decimal("0.01")):
        raise GrantMismatch("Grant amount does not match this payment")
    if grant.currency.upper() != currency.upper():
        raise GrantMismatch("Grant currency does not match this payment")
    if require_unused and grant.used_at is not None:
        raise GrantInvalid("Authorization grant has already been used")
    return grant


def verify_grant(
    db: Session,
    *,
    token: str,
    amount: Decimal,
    currency: str,
    secret: str,
    now: datetime | None = None,
) -> AuthorizationGrant:
    return authenticate_grant(
        db,
        token=token,
        amount=amount,
        currency=currency,
        secret=secret,
        now=now,
        require_unused=True,
    )
