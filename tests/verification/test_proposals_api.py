from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apps.api.deps import get_db
from apps.api.main import app
from apps.api.models.db import Base


@pytest.fixture
def api_client() -> Generator[TestClient, None, None]:
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


def _active_laptop(client: TestClient) -> str:
    compiled = client.post(
        "/v1/intents/compile",
        json={"raw_request": "Buy a programming laptop under 60000"},
    )
    assert compiled.status_code == 200, compiled.text
    intent_id = compiled.json()["intent_id"]
    confirmed = client.post("/v1/intents/", json={"intent_id": intent_id})
    assert confirmed.status_code == 200, confirmed.text
    return intent_id


def _proposal(amount: int) -> dict:
    return {
        "amount": amount,
        "currency": "INR",
        "merchant": "demo_catalog",
        "product": {
            "id": "sku_laptop",
            "name": "Programming laptop",
            "category": "laptop",
        },
    }


def test_proposal_under_budget_passes(api_client: TestClient) -> None:
    intent_id = _active_laptop(api_client)
    response = api_client.post(f"/v1/intents/{intent_id}/proposals", json=_proposal(58000))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["hard"]["passed"] is True
    assert body["hard"]["failures"] == []
    assert body["decision"]["verdict"] == "APPROVE"


def test_proposal_over_budget_fails_without_llm(api_client: TestClient) -> None:
    intent_id = _active_laptop(api_client)
    response = api_client.post(f"/v1/intents/{intent_id}/proposals", json=_proposal(85000))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["hard"]["passed"] is False
    assert body["hard"]["failures"][0]["code"] == "budget_exceeded"
    assert body["decision"]["verdict"] == "BLOCK"


def test_high_semantic_cannot_rescue_hard_fail(api_client: TestClient) -> None:
    from apps.api.deps import get_semantic_verifier
    from packages.verification_engine.schemas import SemanticAssessment

    class StubVerifier:
        def verify(self, *_args, **_kwargs):
            return SemanticAssessment(semantic_match=0.99, reason="stub", error=False)

    app.dependency_overrides[get_semantic_verifier] = lambda: StubVerifier()
    try:
        intent_id = _active_laptop(api_client)
        response = api_client.post(f"/v1/intents/{intent_id}/proposals", json=_proposal(85000))
        assert response.status_code == 200, response.text
        assert response.json()["semantic"]["semantic_match"] == 0.99
        assert response.json()["decision"]["verdict"] == "BLOCK"
    finally:
        app.dependency_overrides.pop(get_semantic_verifier, None)


def test_duplicate_proposal_is_hard_fail(api_client: TestClient) -> None:
    intent_id = _active_laptop(api_client)
    first = api_client.post(f"/v1/intents/{intent_id}/proposals", json=_proposal(58000))
    second = api_client.post(f"/v1/intents/{intent_id}/proposals", json=_proposal(58000))
    assert first.json()["hard"]["passed"] is True
    assert second.json()["hard"]["passed"] is False
    assert any(item["code"] == "duplicate_transaction" for item in second.json()["hard"]["failures"])
    assert second.json()["decision"]["verdict"] == "BLOCK"


def test_latest_decision_endpoint(api_client: TestClient) -> None:
    intent_id = _active_laptop(api_client)
    missing = api_client.get(f"/v1/intents/{intent_id}/decision")
    assert missing.status_code == 404
    created = api_client.post(f"/v1/intents/{intent_id}/proposals", json=_proposal(58000))
    fetched = api_client.get(f"/v1/intents/{intent_id}/decision")
    assert fetched.status_code == 200, fetched.text
    assert fetched.json()["proposal_id"] == created.json()["proposal_id"]
    assert fetched.json()["decision"]["verdict"] == "APPROVE"


def test_draft_intent_cannot_receive_proposal(api_client: TestClient) -> None:
    compiled = api_client.post(
        "/v1/intents/compile",
        json={"raw_request": "Buy a programming laptop under 60000"},
    )
    intent_id = compiled.json()["intent_id"]
    response = api_client.post(f"/v1/intents/{intent_id}/proposals", json=_proposal(58000))
    assert response.status_code == 409


def test_preferred_brand_substitution_pauses(api_client: TestClient) -> None:
    compiled = api_client.post(
        "/v1/intents/compile",
        json={"raw_request": "Buy wireless headphones under 5000, preferably Sony or JBL"},
    )
    assert compiled.status_code == 200, compiled.text
    intent_id = compiled.json()["intent_id"]
    confirmed = api_client.post("/v1/intents/", json={"intent_id": intent_id})
    assert confirmed.status_code == 200, confirmed.text
    response = api_client.post(
        f"/v1/intents/{intent_id}/proposals",
        json={
            "amount": 4500,
            "currency": "INR",
            "merchant": "demo_catalog",
            "product": {
                "id": "sku_bose",
                "name": "Bose QuietComfort",
                "category": "headphones",
            },
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["hard"]["passed"] is True
    assert body["semantic"]["substitution_severity"] == "major"
    assert body["decision"]["verdict"] == "PAUSE"
