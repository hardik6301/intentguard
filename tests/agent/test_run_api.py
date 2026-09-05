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


def _active(client: TestClient, raw: str) -> str:
    compiled = client.post("/v1/intents/compile", json={"raw_request": raw})
    assert compiled.status_code == 200, compiled.text
    intent_id = compiled.json()["intent_id"]
    confirmed = client.post("/v1/intents/", json={"intent_id": intent_id})
    assert confirmed.status_code == 200, confirmed.text
    return intent_id


def test_run_laptop_proposes_and_decides(api_client: TestClient) -> None:
    intent_id = _active(api_client, "Buy a programming laptop under 60000")
    response = api_client.post(f"/v1/intents/{intent_id}/run")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["would_charge"] is False
    assert body["evaluation"]["proposal"]["amount"] <= 60000
    assert body["evaluation"]["proposal"]["product"]["id"] != "sku_poison_deal"
    assert body["evaluation"]["decision"]["verdict"] == "APPROVE"
    assert body["evaluation"]["grant"] is not None
    assert body["evaluation"]["grant"]["token"]
    activity = api_client.get(f"/v1/intents/{intent_id}/activity")
    assert activity.status_code == 200
    types = [item["event_type"] for item in activity.json()]
    assert "agent_started" in types
    assert "decision_made" in types


def test_poisoned_page_cannot_approve_or_charge(api_client: TestClient) -> None:
    intent_id = _active(api_client, "Buy the Ultra Deal programming laptop under 60000")
    response = api_client.post(f"/v1/intents/{intent_id}/run")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["evaluation"]["proposal"]["product"]["id"] == "sku_poison_deal"
    assert body["evaluation"]["risk"]["injection_high"] is True
    assert body["evaluation"]["decision"]["verdict"] == "BLOCK"
    assert body["would_charge"] is False
    assert body["evaluation"]["grant"] is None


def test_draft_cannot_run(api_client: TestClient) -> None:
    compiled = api_client.post(
        "/v1/intents/compile",
        json={"raw_request": "Buy a programming laptop under 60000"},
    )
    intent_id = compiled.json()["intent_id"]
    response = api_client.post(f"/v1/intents/{intent_id}/run")
    assert response.status_code == 409


def test_agent_source_tree_has_no_payment_import() -> None:
    root = Path(__file__).resolve().parents[2] / "packages" / "commerce_agent"
    blob = "\n".join(path.read_text() for path in root.glob("*.py"))
    assert "from packages.payment_gateway" not in blob
    assert "import packages.payment_gateway" not in blob
    assert "razorpay" not in blob.casefold()
