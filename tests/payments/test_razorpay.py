from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apps.api.deps import get_db
from apps.api.main import app
from apps.api.models.db import Base
from packages.payment_gateway.razorpay_client import (
    FakeRazorpay,
    reset_razorpay,
    set_razorpay_client,
)
from packages.payment_gateway.simulated import get_ledger, reset_ledger


@pytest.fixture
def fake_razorpay() -> Generator[FakeRazorpay, None, None]:
    reset_ledger()
    reset_razorpay()
    fake = FakeRazorpay()
    set_razorpay_client(fake)
    yield fake
    reset_razorpay()
    reset_ledger()


@pytest.fixture
def api_client(fake_razorpay: FakeRazorpay) -> Generator[TestClient, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(engine)

    def override_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def _active(client: TestClient, raw: str) -> str:
    compiled = client.post("/v1/intents/compile", json={"raw_request": raw})
    assert compiled.status_code == 200, compiled.text
    intent_id = compiled.json()["intent_id"]
    confirmed = client.post("/v1/intents/", json={"intent_id": intent_id})
    assert confirmed.status_code == 200, confirmed.text
    return intent_id


def _approve(client: TestClient) -> dict:
    intent_id = _active(client, "Buy a programming laptop under 60000")
    response = client.post(f"/v1/intents/{intent_id}/run")
    assert response.status_code == 200, response.text
    return response.json()["evaluation"]


def test_config_falls_back_to_simulated_without_keys(api_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    reset_razorpay()
    monkeypatch.setenv("PAYMENT_PROVIDER", "razorpay")
    monkeypatch.setenv("RAZORPAY_KEY_ID", "")
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", "")
    response = api_client.get("/v1/payments/config")
    assert response.status_code == 200
    assert response.json()["provider"] == "simulated"
    assert response.json()["razorpay_key_id"] is None


def test_missing_grant_does_not_create_razorpay_order(
    api_client: TestClient, fake_razorpay: FakeRazorpay
) -> None:
    before = fake_razorpay.create_calls
    response = api_client.post(
        "/v1/payments",
        json={"amount": 54990, "currency": "INR", "idempotency_key": "rzp-missing-grant-01"},
    )
    assert response.status_code == 403
    assert fake_razorpay.create_calls == before
    assert fake_razorpay.orders == {}
    assert get_ledger().succeeded_count() == 0


def test_approve_creates_pending_checkout_not_success(
    api_client: TestClient, fake_razorpay: FakeRazorpay
) -> None:
    evaluation = _approve(api_client)
    token = evaluation["grant"]["token"]
    created = api_client.post(
        "/v1/payments",
        json={
            "grant_token": token,
            "amount": evaluation["proposal"]["amount"],
            "currency": "INR",
            "idempotency_key": "rzp-checkout-01",
        },
    )
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["provider"] == "razorpay"
    assert body["status"] == "pending"
    assert body["checkout"]["order_id"].startswith("order_")
    assert body["checkout"]["amount_paise"] == 5499000
    assert get_ledger().succeeded_count() == 0
    assert fake_razorpay.create_calls == 1


def test_confirm_checkout_marks_succeeded(
    api_client: TestClient, fake_razorpay: FakeRazorpay
) -> None:
    evaluation = _approve(api_client)
    created = api_client.post(
        "/v1/payments",
        json={
            "grant_token": evaluation["grant"]["token"],
            "amount": evaluation["proposal"]["amount"],
            "currency": "INR",
            "idempotency_key": "rzp-confirm-01",
        },
    ).json()
    order_id = created["checkout"]["order_id"]
    payment_id = "pay_test_confirm"
    signature = fake_razorpay.sign_checkout(order_id, payment_id)
    confirmed = api_client.post(
        f"/v1/payments/{created['id']}/confirm",
        json={
            "razorpay_order_id": order_id,
            "razorpay_payment_id": payment_id,
            "razorpay_signature": signature,
        },
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["status"] == "succeeded"
    assert confirmed.json()["checkout"] is None
    fetched = api_client.get(f"/v1/payments/{created['id']}")
    assert fetched.json()["status"] == "succeeded"


def test_webhook_captures_without_second_order(
    api_client: TestClient, fake_razorpay: FakeRazorpay
) -> None:
    evaluation = _approve(api_client)
    created = api_client.post(
        "/v1/payments",
        json={
            "grant_token": evaluation["grant"]["token"],
            "amount": evaluation["proposal"]["amount"],
            "currency": "INR",
            "idempotency_key": "rzp-webhook-01",
        },
    ).json()
    order_id = created["checkout"]["order_id"]
    payload = {
        "event": "payment.captured",
        "payload": {"payment": {"entity": {"id": "pay_hook", "order_id": order_id, "status": "captured"}}},
    }
    import json

    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    hook = api_client.post(
        "/v1/payments/webhook",
        content=raw,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": fake_razorpay.sign_webhook(raw)},
    )
    assert hook.status_code == 200, hook.text
    assert hook.json()["status"] == "ok"
    fetched = api_client.get(f"/v1/payments/{created['id']}")
    assert fetched.json()["status"] == "succeeded"
    assert fake_razorpay.create_calls == 1


def test_poll_after_provider_paid_does_not_create_second_order(
    api_client: TestClient, fake_razorpay: FakeRazorpay
) -> None:
    evaluation = _approve(api_client)
    created = api_client.post(
        "/v1/payments",
        json={
            "grant_token": evaluation["grant"]["token"],
            "amount": evaluation["proposal"]["amount"],
            "currency": "INR",
            "idempotency_key": "rzp-poll-01",
        },
    ).json()
    fake_razorpay.mark_paid(created["checkout"]["order_id"])
    fetched = api_client.get(f"/v1/payments/{created['id']}")
    assert fetched.json()["status"] == "succeeded"
    assert fake_razorpay.create_calls == 1


def test_blocked_session_never_returns_checkout(api_client: TestClient, fake_razorpay: FakeRazorpay) -> None:
    intent_id = _active(api_client, "Buy the Ultra Deal programming laptop under 60000")
    run = api_client.post(f"/v1/intents/{intent_id}/run")
    evaluation = run.json()["evaluation"]
    assert evaluation["decision"]["verdict"] == "BLOCK"
    assert evaluation["grant"] is None
    assert evaluation["payment"] is None
    decision = api_client.get(f"/v1/intents/{intent_id}/decision").json()
    assert decision["grant"] is None
    assert decision.get("payment") is None
    assert fake_razorpay.orders == {}


def test_agent_source_still_cannot_call_razorpay() -> None:
    root = Path(__file__).resolve().parents[2] / "packages" / "commerce_agent"
    blob = "\n".join(path.read_text() for path in root.glob("*.py"))
    assert "razorpay" not in blob.casefold()
    assert "from packages.payment_gateway" not in blob
    assert "checkout.razorpay.com" not in blob
