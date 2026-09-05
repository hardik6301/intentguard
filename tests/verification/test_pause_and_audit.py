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

HEADPHONES = "Buy wireless headphones under 5000, preferably Sony or JBL"
BOSE = {
    "amount": 4500,
    "currency": "INR",
    "merchant": "demo_catalog",
    "product": {
        "id": "sku_bose",
        "name": "Bose QuietComfort",
        "category": "headphones",
    },
}


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


def _pause_bose(client: TestClient) -> dict:
    intent_id = _active(client, HEADPHONES)
    response = client.post(f"/v1/intents/{intent_id}/proposals", json=BOSE)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["decision"]["verdict"] == "PAUSE"
    assert body["resolution"] == "pending"
    assert body["grant"] is None
    assert body["decision_id"]
    return body


def test_pause_does_not_mint_grant_or_allow_payment(api_client: TestClient) -> None:
    body = _pause_bose(api_client)
    before = get_ledger().succeeded_count()
    pay = api_client.post(
        "/v1/payments",
        json={
            "amount": body["proposal"]["amount"],
            "currency": "INR",
            "idempotency_key": "idem-pause-pending-01",
        },
    )
    assert pay.status_code == 403, pay.text
    assert get_ledger().succeeded_count() == before
    latest = api_client.get(f"/v1/intents/{body['intent_id']}/decision")
    assert latest.json()["resolution"] == "pending"
    assert latest.json()["grant"] is None


def test_pause_confirm_mints_grant_and_payment_succeeds(api_client: TestClient) -> None:
    body = _pause_bose(api_client)
    confirmed = api_client.post(
        f"/v1/decisions/{body['decision_id']}/confirm",
        json={"action": "confirm"},
    )
    assert confirmed.status_code == 200, confirmed.text
    payload = confirmed.json()
    assert payload["resolution"] == "confirmed"
    assert payload["decision"]["verdict"] == "PAUSE"
    assert payload["grant"] is not None
    assert payload["grant"]["token"]
    pay = api_client.post(
        "/v1/payments",
        json={
            "grant_token": payload["grant"]["token"],
            "amount": payload["proposal"]["amount"],
            "currency": "INR",
            "idempotency_key": "idem-pause-confirm-01",
        },
    )
    assert pay.status_code == 200, pay.text
    assert pay.json()["status"] == "succeeded"
    assert get_ledger().succeeded_count() == 1
    again = api_client.post(
        f"/v1/decisions/{body['decision_id']}/confirm",
        json={"action": "confirm"},
    )
    assert again.status_code == 409


def test_pause_reject_blocks_without_grant(api_client: TestClient) -> None:
    body = _pause_bose(api_client)
    rejected = api_client.post(
        f"/v1/decisions/{body['decision_id']}/confirm",
        json={"action": "reject"},
    )
    assert rejected.status_code == 200, rejected.text
    payload = rejected.json()
    assert payload["resolution"] == "rejected"
    assert payload["grant"] is None
    assert "User rejected the proposed action." in payload["decision"]["reasons"]
    pay = api_client.post(
        "/v1/payments",
        json={
            "amount": payload["proposal"]["amount"],
            "currency": "INR",
            "idempotency_key": "idem-pause-reject-01",
        },
    )
    assert pay.status_code == 403
    events = api_client.get(f"/v1/intents/{body['intent_id']}/audit").json()
    types = [item["event_type"] for item in events]
    assert "pause_rejected" in types
    assert "payment_not_initiated" in types
    assert "grant_minted" not in types
    later = api_client.post(
        f"/v1/decisions/{body['decision_id']}/confirm",
        json={"action": "confirm"},
    )
    assert later.status_code == 409


def test_confirm_on_block_is_conflict(api_client: TestClient) -> None:
    intent_id = _active(api_client, "Buy a programming laptop under 60000")
    blocked = api_client.post(
        f"/v1/intents/{intent_id}/proposals",
        json={
            "amount": 85000,
            "currency": "INR",
            "merchant": "demo_catalog",
            "product": {"id": "sku_laptop", "name": "Programming laptop", "category": "laptop"},
        },
    )
    assert blocked.json()["decision"]["verdict"] == "BLOCK"
    decision_id = blocked.json()["decision_id"]
    response = api_client.post(f"/v1/decisions/{decision_id}/confirm", json={"action": "confirm"})
    assert response.status_code == 409


def test_budget_block_audit_is_complete(api_client: TestClient) -> None:
    intent_id = _active(api_client, "Buy a programming laptop under 60000")
    blocked = api_client.post(
        f"/v1/intents/{intent_id}/proposals",
        json={
            "amount": 85000,
            "currency": "INR",
            "merchant": "demo_catalog",
            "product": {"id": "sku_laptop", "name": "Programming laptop", "category": "laptop"},
        },
    )
    assert blocked.json()["decision"]["verdict"] == "BLOCK"
    events = api_client.get(f"/v1/intents/{intent_id}/audit")
    assert events.status_code == 200, events.text
    rows = events.json()
    types = [item["event_type"] for item in rows]
    assert "intent_compiled" in types
    assert "intent_activated" in types
    assert "proposal_submitted" in types
    assert "hard_constraints_checked" in types
    assert "semantic_assessed" in types
    assert "risk_assessed" in types
    assert "decision_made" in types
    assert "payment_not_initiated" in types
    assert "payment_succeeded" not in types
    decision = next(item for item in rows if item["event_type"] == "decision_made")
    assert decision["payload"]["verdict"] == "BLOCK"
    assert decision["tone"] == "block"
    unpaid = next(item for item in rows if item["event_type"] == "payment_not_initiated")
    assert unpaid["title"] == "Payment was not initiated"
    assert unpaid["tone"] == "block"
    assert rows[0]["event_type"] == "intent_compiled"
    ids = [item["id"] for item in rows]
    assert ids == sorted(ids)
