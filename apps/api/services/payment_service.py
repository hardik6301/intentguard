from __future__ import annotations

import hmac as hmac_mod
import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.config import get_settings
from apps.api.models.db import (
    AuthorizationGrant,
    Intent,
    IntentStatus,
    Payment,
    PaymentStatus,
)
from apps.api.services import audit_service
from packages.payment_gateway.errors import CheckoutError, GrantInvalid, ProviderTimeout
from packages.payment_gateway.grants import authenticate_grant
from packages.payment_gateway.razorpay_client import (
    FakeRazorpay,
    amount_to_paise,
    checkout_session,
    get_razorpay_client,
    payment_signature,
    webhook_signature,
)
from packages.payment_gateway.schemas import CheckoutSession, PaymentRecord
from packages.payment_gateway.simulated import get_ledger


class PaymentNotFound(Exception):
    pass


def effective_provider() -> str:
    from packages.payment_gateway import razorpay_client as razorpay_mod

    if razorpay_mod._OVERRIDE is not None:
        return "razorpay"
    settings = get_settings()
    if (
        settings.payment_provider == "razorpay"
        and settings.razorpay_key_id
        and settings.razorpay_key_secret
    ):
        return "razorpay"
    return "simulated"


def payment_config() -> dict[str, str | None]:
    provider = effective_provider()
    client = get_razorpay_client() if provider == "razorpay" else None
    return {
        "provider": provider,
        "razorpay_key_id": client.key_id if client is not None else None,
    }


def _checkout_for(row: Payment) -> CheckoutSession | None:
    if row.provider != "razorpay" or row.status not in {
        PaymentStatus.PENDING.value,
        PaymentStatus.CREATED.value,
        PaymentStatus.UNKNOWN.value,
    }:
        return None
    if not row.provider_ref:
        return None
    client = get_razorpay_client()
    if client is None:
        return None
    order = client.fetch_order(row.provider_ref)
    if order is None:
        return None
    return checkout_session(client, order)


def _record(row: Payment, grant: AuthorizationGrant) -> PaymentRecord:
    return PaymentRecord(
        id=row.id,
        grant_id=row.grant_id,
        intent_id=grant.intent_id,
        provider=row.provider,
        provider_ref=row.provider_ref,
        idempotency_key=row.idempotency_key,
        status=row.status,
        amount=Decimal(row.amount),
        currency=grant.currency,
        checkout=_checkout_for(row),
    )


def _mark_intent_paid(db: Session, intent_id: UUID) -> None:
    intent = db.get(Intent, intent_id)
    if intent is not None:
        intent.status = IntentStatus.PAID.value


def _apply_success(db: Session, row: Payment, grant: AuthorizationGrant, provider_ref: str) -> None:
    row.status = PaymentStatus.SUCCEEDED.value
    row.provider_ref = provider_ref
    _mark_intent_paid(db, grant.intent_id)
    audit_service.record(
        db,
        intent_id=grant.intent_id,
        actor="payment",
        event_type="payment_succeeded",
        payload={"payment_id": str(row.id), "provider_ref": provider_ref, "provider": row.provider},
    )


def _charge_simulated(
    db: Session,
    row: Payment,
    grant: AuthorizationGrant,
    *,
    force_timeout: bool,
    timeout_committed: bool,
) -> Payment:
    ledger = get_ledger()
    if force_timeout:
        ledger.arm_timeout(committed=timeout_committed)
    try:
        created = ledger.create(
            amount=Decimal(row.amount),
            currency=grant.currency,
            idempotency_key=row.idempotency_key,
        )
    except ProviderTimeout as exc:
        row.status = PaymentStatus.UNKNOWN.value
        row.provider_ref = exc.provider_ref
        audit_service.record(
            db,
            intent_id=grant.intent_id,
            actor="payment",
            event_type="payment_timeout",
            payload={"payment_id": str(row.id), "provider_ref": exc.provider_ref},
        )
        return row
    _apply_success(db, row, grant, created.provider_ref)
    return row


def _charge_razorpay(
    db: Session,
    row: Payment,
    grant: AuthorizationGrant,
    *,
    force_timeout: bool,
    timeout_committed: bool,
) -> Payment:
    client = get_razorpay_client()
    if client is None:
        row.provider = "simulated"
        return _charge_simulated(
            db, row, grant, force_timeout=force_timeout, timeout_committed=timeout_committed
        )
    if force_timeout and isinstance(client, FakeRazorpay):
        client.arm_timeout(committed=timeout_committed)
    try:
        order = client.create_order(
            amount_paise=amount_to_paise(row.amount),
            currency=grant.currency,
            receipt=row.idempotency_key,
            notes={
                "intent_id": str(grant.intent_id),
                "grant_id": str(grant.id),
                "payment_id": str(row.id),
            },
        )
    except ProviderTimeout as exc:
        row.status = PaymentStatus.UNKNOWN.value
        row.provider_ref = exc.provider_ref
        audit_service.record(
            db,
            intent_id=grant.intent_id,
            actor="payment",
            event_type="payment_timeout",
            payload={"payment_id": str(row.id), "provider_ref": exc.provider_ref, "provider": "razorpay"},
        )
        return row
    row.provider_ref = order.order_id
    if order.status == "paid":
        _apply_success(db, row, grant, order.order_id)
        return row
    row.status = PaymentStatus.PENDING.value
    audit_service.record(
        db,
        intent_id=grant.intent_id,
        actor="payment",
        event_type="razorpay_order_created",
        payload={"payment_id": str(row.id), "order_id": order.order_id},
    )
    return row


def _reconcile_simulated(db: Session, row: Payment, grant: AuthorizationGrant) -> Payment:
    ledger = get_ledger()
    found = ledger.fetch_by_idempotency(row.idempotency_key) or ledger.fetch(row.provider_ref)
    if found is not None and found.status == "succeeded":
        _apply_success(db, row, grant, found.provider_ref)
        return row
    if found is not None and found.status == "failed":
        row.status = PaymentStatus.FAILED.value
        row.provider_ref = found.provider_ref
        return row
    if found is not None and found.status == "pending":
        row.status = PaymentStatus.PENDING.value
        row.provider_ref = found.provider_ref
        return row
    try:
        created = ledger.create(
            amount=Decimal(row.amount),
            currency=grant.currency,
            idempotency_key=row.idempotency_key,
        )
    except ProviderTimeout as exc:
        row.status = PaymentStatus.UNKNOWN.value
        if exc.provider_ref:
            row.provider_ref = exc.provider_ref
        audit_service.record(
            db,
            intent_id=grant.intent_id,
            actor="payment",
            event_type="payment_timeout",
            payload={"payment_id": str(row.id), "provider_ref": exc.provider_ref},
        )
        return row
    _apply_success(db, row, grant, created.provider_ref)
    return row


def _reconcile_razorpay(db: Session, row: Payment, grant: AuthorizationGrant) -> Payment:
    client = get_razorpay_client()
    if client is None:
        return row
    order = client.fetch_order(row.provider_ref) if row.provider_ref else None
    if order is not None and order.status == "paid":
        _apply_success(db, row, grant, order.order_id)
        return row
    if order is not None:
        row.status = PaymentStatus.PENDING.value
        row.provider_ref = order.order_id
        return row
    try:
        created = client.create_order(
            amount_paise=amount_to_paise(row.amount),
            currency=grant.currency,
            receipt=row.idempotency_key,
            notes={"intent_id": str(grant.intent_id), "payment_id": str(row.id)},
        )
    except ProviderTimeout as exc:
        row.status = PaymentStatus.UNKNOWN.value
        if exc.provider_ref:
            row.provider_ref = exc.provider_ref
        return row
    row.provider_ref = created.order_id
    if created.status == "paid":
        _apply_success(db, row, grant, created.order_id)
        return row
    row.status = PaymentStatus.PENDING.value
    return row


def _reconcile_row(db: Session, row: Payment, grant: AuthorizationGrant) -> Payment:
    if row.status in {PaymentStatus.SUCCEEDED.value, PaymentStatus.FAILED.value}:
        return row
    if row.provider == "razorpay":
        return _reconcile_razorpay(db, row, grant)
    return _reconcile_simulated(db, row, grant)


def create_payment(
    db: Session,
    *,
    grant_token: str,
    amount: Decimal,
    currency: str,
    idempotency_key: str,
    force_timeout: bool = False,
    timeout_committed: bool = False,
) -> PaymentRecord:
    settings = get_settings()
    grant = authenticate_grant(
        db,
        token=grant_token,
        amount=amount,
        currency=currency,
        secret=settings.grant_signing_secret,
        require_unused=False,
    )
    existing = db.scalars(
        select(Payment).where(Payment.idempotency_key == idempotency_key)
    ).first()
    if existing is not None:
        if existing.grant_id != grant.id:
            raise GrantInvalid("Idempotency key is bound to a different grant")
        row = _reconcile_row(db, existing, grant)
        db.commit()
        db.refresh(row)
        return _record(row, grant)

    owned = db.scalars(select(Payment).where(Payment.grant_id == grant.id)).first()
    if owned is not None:
        row = _reconcile_row(db, owned, grant)
        db.commit()
        db.refresh(row)
        return _record(row, grant)
    if grant.used_at is not None:
        raise GrantInvalid("Authorization grant has already been used")

    provider = effective_provider()
    moment = datetime.now(timezone.utc)
    grant.used_at = moment
    row = Payment(
        id=uuid4(),
        grant_id=grant.id,
        provider=provider,
        provider_ref=None,
        idempotency_key=idempotency_key,
        status=PaymentStatus.PENDING.value,
        amount=Decimal(amount).quantize(Decimal("0.01")),
    )
    db.add(row)
    audit_service.record(
        db,
        intent_id=grant.intent_id,
        actor="payment",
        event_type="payment_created",
        payload={"payment_id": str(row.id), "idempotency_key": idempotency_key, "provider": provider},
    )
    db.flush()

    if provider == "razorpay":
        _charge_razorpay(
            db, row, grant, force_timeout=force_timeout, timeout_committed=timeout_committed
        )
    else:
        _charge_simulated(
            db, row, grant, force_timeout=force_timeout, timeout_committed=timeout_committed
        )
    db.commit()
    db.refresh(row)
    return _record(row, grant)


def get_payment(db: Session, payment_id: UUID) -> PaymentRecord:
    row = db.get(Payment, payment_id)
    if row is None:
        raise PaymentNotFound()
    grant = db.get(AuthorizationGrant, row.grant_id)
    if grant is None:
        raise PaymentNotFound()
    row = _reconcile_row(db, row, grant)
    db.commit()
    db.refresh(row)
    return _record(row, grant)


def latest_payment_for_intent(db: Session, intent_id: UUID) -> PaymentRecord | None:
    grant = db.scalars(
        select(AuthorizationGrant)
        .where(AuthorizationGrant.intent_id == intent_id)
        .order_by(AuthorizationGrant.expires_at.desc())
    ).first()
    if grant is None or grant.payment is None:
        return None
    row = _reconcile_row(db, grant.payment, grant)
    db.commit()
    db.refresh(row)
    return _record(row, grant)


def confirm_checkout(
    db: Session,
    payment_id: UUID,
    *,
    razorpay_order_id: str,
    razorpay_payment_id: str,
    razorpay_signature: str,
) -> PaymentRecord:
    row = db.get(Payment, payment_id)
    if row is None:
        raise PaymentNotFound()
    grant = db.get(AuthorizationGrant, row.grant_id)
    if grant is None:
        raise PaymentNotFound()
    if row.provider != "razorpay":
        raise CheckoutError("This payment is not a Razorpay checkout")
    if row.provider_ref and row.provider_ref != razorpay_order_id:
        raise CheckoutError("Order id does not match this payment")
    client = get_razorpay_client()
    if client is None:
        raise CheckoutError("Razorpay is not configured", status_code=503)
    expected = payment_signature(razorpay_order_id, razorpay_payment_id, client.secret)
    if (
        not razorpay_signature
        or len(razorpay_signature) != len(expected)
        or not hmac_mod.compare_digest(razorpay_signature, expected)
    ):
        raise CheckoutError("Razorpay signature is invalid")
    if isinstance(client, FakeRazorpay):
        client.mark_paid(razorpay_order_id)
    else:
        order = client.fetch_order(razorpay_order_id)
        if order is None or order.status != "paid":
            row.status = PaymentStatus.PENDING.value
            db.commit()
            return _record(row, grant)
    _apply_success(db, row, grant, razorpay_order_id)
    db.commit()
    db.refresh(row)
    return _record(row, grant)


def apply_webhook(db: Session, *, raw_body: bytes, signature: str) -> dict[str, str]:
    client = get_razorpay_client()
    settings = get_settings()
    secret = client.secret if client is not None else settings.razorpay_key_secret
    if not secret:
        return {"status": "ignored"}
    expected = webhook_signature(raw_body, secret)
    if not signature or len(signature) != len(expected) or not hmac_mod.compare_digest(signature, expected):
        raise CheckoutError("Webhook signature is invalid")
    payload = json.loads(raw_body.decode("utf-8"))
    if not isinstance(payload, dict):
        raise CheckoutError("Webhook payload must be an object")
    event = str(payload.get("event") or "")
    entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
    if event not in {"payment.captured", "order.paid"} and str(entity.get("status") or "") != "captured":
        return {"status": "ignored"}
    order_id = str(entity.get("order_id") or "")
    if not order_id:
        return {"status": "ignored"}
    row = db.scalars(select(Payment).where(Payment.provider_ref == order_id)).first()
    if row is None:
        return {"status": "ignored"}
    grant = db.get(AuthorizationGrant, row.grant_id)
    if grant is None:
        return {"status": "ignored"}
    if isinstance(client, FakeRazorpay):
        client.mark_paid(order_id)
    _apply_success(db, row, grant, order_id)
    db.commit()
    return {"status": "ok"}
