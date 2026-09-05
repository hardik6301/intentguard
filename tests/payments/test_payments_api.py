from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apps.api.deps import get_db
from apps.api.main import app
from apps.api.models.db import Base
from packages.payment_gateway.simulated import get_ledger, reset_ledger


@pytest.fixture
def api_client() -> Generator[TestClient, None, None]:
    reset_ledger()
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
    reset_ledger()


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
    body = response.json()
    assert body["evaluation"]["decision"]["verdict"] == "APPROVE"
    assert body["evaluation"]["grant"]["token"]
    return body


def test_payment_without_grant_is_forbidden(api_client: TestClient) -> None:
    before = get_ledger().succeeded_count()
    response = api_client.post(
        "/v1/payments",
        json={
            "amount": 54990,
            "currency": "INR",
            "idempotency_key": "idem-missing-grant-01",
        },
    )
    assert response.status_code == 403, response.text
    assert get_ledger().succeeded_count() == before


def test_approve_mints_grant_and_payment_succeeds(api_client: TestClient) -> None:
    run = _approve(api_client)
    evaluation = run["evaluation"]
    token = evaluation["grant"]["token"]
    amount = evaluation["proposal"]["amount"]
    response = api_client.post(
        "/v1/payments",
        json={
            "grant_token": token,
            "amount": amount,
            "currency": "INR",
            "idempotency_key": "idem-laptop-success-01",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "succeeded"
    assert body["provider"] == "simulated"
    assert get_ledger().succeeded_count() == 1
    fetched = api_client.get(f"/v1/payments/{body['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["status"] == "succeeded"


def test_blocked_decision_never_creates_payment_or_grant(api_client: TestClient) -> None:
    intent_id = _active(api_client, "Buy the Ultra Deal programming laptop under 60000")
    run = api_client.post(f"/v1/intents/{intent_id}/run")
    assert run.status_code == 200, run.text
    evaluation = run.json()["evaluation"]
    assert evaluation["decision"]["verdict"] == "BLOCK"
    assert evaluation["grant"] is None
    assert evaluation["payment"] is None
    before = get_ledger().succeeded_count()
    response = api_client.post(
        "/v1/payments",
        json={
            "amount": evaluation["proposal"]["amount"],
            "currency": "INR",
            "idempotency_key": "idem-blocked-01",
        },
    )
    assert response.status_code == 403
    assert get_ledger().succeeded_count() == before
    decision = api_client.get(f"/v1/intents/{intent_id}/decision")
    assert decision.json()["grant"] is None
    assert decision.json()["payment"] is None


def test_amount_mismatch_is_forbidden(api_client: TestClient) -> None:
    run = _approve(api_client)
    token = run["evaluation"]["grant"]["token"]
    before = get_ledger().succeeded_count()
    response = api_client.post(
        "/v1/payments",
        json={
            "grant_token": token,
            "amount": 1,
            "currency": "INR",
            "idempotency_key": "idem-mismatch-01",
        },
    )
    assert response.status_code == 403, response.text
    assert get_ledger().succeeded_count() == before


def test_duplicate_fingerprint_blocks_after_approval(api_client: TestClient) -> None:
    intent_id = _active(api_client, "Buy a programming laptop under 60000")
    first = api_client.post(f"/v1/intents/{intent_id}/run")
    assert first.json()["evaluation"]["decision"]["verdict"] == "APPROVE"
    proposal = first.json()["evaluation"]["proposal"]
    second = api_client.post(
        f"/v1/intents/{intent_id}/proposals",
        json={
            "amount": proposal["amount"],
            "currency": proposal["currency"],
            "merchant": proposal["merchant"],
            "product": {
                "id": proposal["product"]["id"],
                "name": proposal["product"]["name"],
                "category": proposal["product"]["category"],
            },
        },
    )
    assert second.status_code == 200, second.text
    assert second.json()["hard"]["passed"] is False
    assert any(item["code"] == "duplicate_transaction" for item in second.json()["hard"]["failures"])
    assert second.json()["decision"]["verdict"] == "BLOCK"
    assert second.json()["grant"] is None
