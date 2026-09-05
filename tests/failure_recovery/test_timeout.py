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


def _grant(client: TestClient) -> dict:
    compiled = client.post(
        "/v1/intents/compile",
        json={"raw_request": "Buy a programming laptop under 60000"},
    )
    intent_id = compiled.json()["intent_id"]
    client.post("/v1/intents/", json={"intent_id": intent_id})
    run = client.post(f"/v1/intents/{intent_id}/run")
    assert run.status_code == 200, run.text
    evaluation = run.json()["evaluation"]
    assert evaluation["grant"]["token"]
    return evaluation


def test_timeout_then_reconcile_creates_one_success(api_client: TestClient) -> None:
    evaluation = _grant(api_client)
    token = evaluation["grant"]["token"]
    amount = evaluation["proposal"]["amount"]
    created = api_client.post(
        "/v1/payments",
        json={
            "grant_token": token,
            "amount": amount,
            "currency": "INR",
            "idempotency_key": "idem-timeout-empty-01",
            "force_timeout": True,
            "timeout_committed": False,
        },
    )
    assert created.status_code == 200, created.text
    assert created.json()["status"] == "unknown"
    assert get_ledger().succeeded_count() == 0
    payment_id = created.json()["id"]
    reconciled = api_client.get(f"/v1/payments/{payment_id}")
    assert reconciled.status_code == 200, reconciled.text
    assert reconciled.json()["status"] == "succeeded"
    assert get_ledger().succeeded_count() == 1
    again = api_client.post(
        "/v1/payments",
        json={
            "grant_token": token,
            "amount": amount,
            "currency": "INR",
            "idempotency_key": "idem-timeout-empty-01",
        },
    )
    assert again.json()["status"] == "succeeded"
    assert again.json()["id"] == payment_id
    assert get_ledger().succeeded_count() == 1


def test_timeout_after_provider_commit_does_not_double_charge(api_client: TestClient) -> None:
    evaluation = _grant(api_client)
    token = evaluation["grant"]["token"]
    amount = evaluation["proposal"]["amount"]
    created = api_client.post(
        "/v1/payments",
        json={
            "grant_token": token,
            "amount": amount,
            "currency": "INR",
            "idempotency_key": "idem-timeout-committed-01",
            "force_timeout": True,
            "timeout_committed": True,
        },
    )
    assert created.status_code == 200, created.text
    assert created.json()["status"] == "unknown"
    assert get_ledger().succeeded_count() == 1
    payment_id = created.json()["id"]
    reconciled = api_client.get(f"/v1/payments/{payment_id}")
    assert reconciled.json()["status"] == "succeeded"
    assert get_ledger().succeeded_count() == 1
    retry = api_client.post(
        "/v1/payments",
        json={
            "grant_token": token,
            "amount": amount,
            "currency": "INR",
            "idempotency_key": "idem-timeout-committed-01",
        },
    )
    assert retry.json()["id"] == payment_id
    assert retry.json()["status"] == "succeeded"
    assert get_ledger().succeeded_count() == 1
