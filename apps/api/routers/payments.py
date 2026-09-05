from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from apps.api.deps import get_db
from apps.api.services import payment_service
from packages.payment_gateway.errors import CheckoutError, GrantError
from packages.payment_gateway.razorpay_client import FakeRazorpay, get_razorpay_client
from packages.payment_gateway.schemas import PaymentRecord
from packages.payment_gateway.simulated import get_ledger

router = APIRouter(prefix="/v1/payments", tags=["payments"])


class CreatePaymentRequest(BaseModel):
    grant_token: str = ""
    amount: Decimal = Field(..., gt=0)
    currency: str = "INR"
    idempotency_key: str = Field(..., min_length=8)
    force_timeout: bool = False
    timeout_committed: bool = False


class ConfirmCheckoutRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


class PaymentConfig(BaseModel):
    provider: str
    razorpay_key_id: str | None = None


@router.get("/config", response_model=PaymentConfig)
def read_payment_config() -> PaymentConfig:
    return PaymentConfig.model_validate(payment_service.payment_config())


@router.post("/webhook")
async def razorpay_webhook(request: Request, db: Session = Depends(get_db)) -> dict[str, str]:
    raw = await request.body()
    signature = request.headers.get("X-Razorpay-Signature", "")
    try:
        return payment_service.apply_webhook(db, raw_body=raw, signature=signature)
    except CheckoutError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.post("", response_model=PaymentRecord)
def create_payment(
    body: CreatePaymentRequest,
    db: Session = Depends(get_db),
) -> PaymentRecord:
    ledger_size = get_ledger().succeeded_count()
    client = get_razorpay_client()
    razorpay_calls = client.create_calls if isinstance(client, FakeRazorpay) else 0
    try:
        return payment_service.create_payment(
            db,
            grant_token=body.grant_token,
            amount=body.amount,
            currency=body.currency,
            idempotency_key=body.idempotency_key,
            force_timeout=body.force_timeout,
            timeout_committed=body.timeout_committed,
        )
    except GrantError as exc:
        if get_ledger().succeeded_count() != ledger_size:
            raise RuntimeError("Ledger mutated without a grant") from exc
        if isinstance(client, FakeRazorpay) and client.create_calls != razorpay_calls:
            raise RuntimeError("Razorpay mutated without a grant") from exc
        raise HTTPException(status_code=403, detail=exc.message) from exc


@router.post("/{payment_id}/confirm", response_model=PaymentRecord)
def confirm_payment(
    payment_id: UUID,
    body: ConfirmCheckoutRequest,
    db: Session = Depends(get_db),
) -> PaymentRecord:
    try:
        return payment_service.confirm_checkout(
            db,
            payment_id,
            razorpay_order_id=body.razorpay_order_id,
            razorpay_payment_id=body.razorpay_payment_id,
            razorpay_signature=body.razorpay_signature,
        )
    except payment_service.PaymentNotFound as exc:
        raise HTTPException(status_code=404, detail="Payment not found") from exc
    except CheckoutError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("/{payment_id}", response_model=PaymentRecord)
def read_payment(payment_id: UUID, db: Session = Depends(get_db)) -> PaymentRecord:
    try:
        return payment_service.get_payment(db, payment_id)
    except payment_service.PaymentNotFound as exc:
        raise HTTPException(status_code=404, detail="Payment not found") from exc
