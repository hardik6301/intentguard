from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apps.api.deps import get_db
from apps.api.main import app
from apps.api.models.db import Base
from packages.intent_compiler.broken_client import BrokenJsonClient
from packages.intent_compiler.compiler import IntentCompiler
from packages.intent_compiler.schemas import CompileFailed
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


def _active(client: TestClient, raw: str = "Buy a programming laptop under 60000") -> str:
    compiled = client.post("/v1/intents/compile", json={"raw_request": raw})
    assert compiled.status_code == 200, compiled.text
    intent_id = compiled.json()["intent_id"]
    confirmed = client.post("/v1/intents/", json={"intent_id": intent_id})
    assert confirmed.status_code == 200, confirmed.text
    return intent_id


def test_eval_run_returns_uar_first_fields(api_client: TestClient) -> None:
    response = api_client.post("/v1/eval/run")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "ok"
    assert body["unsafe_approval_rate"] == 0
    assert body["total"] >= 40
    assert "unsafe_approval_rate" in body


def test_eval_catalog_lists_four_prd_failures(api_client: TestClient) -> None:
    response = api_client.get("/v1/eval/failures")
    assert response.status_code == 200
    ids = [item["id"] for item in response.json()["failures"]]
    assert ids == [
        "invalid_compiler_json",
        "low_semantic",
        "prompt_injection",
        "payment_timeout",
    ]


def test_broken_json_client_retries_once_then_fails() -> None:
    client = BrokenJsonClient()
    compiler = IntentCompiler(llm=client)
    with pytest.raises(CompileFailed) as caught:
        compiler.compile("Buy a programming laptop under 60000")
    assert client.calls == 2
    assert "will not invent" in str(caught.value.message).lower()


def test_force_invalid_compiler_json_fails_closed(api_client: TestClient) -> None:
    response = api_client.post(
        "/v1/intents/compile",
        json={
            "raw_request": "Buy a programming laptop under 60000",
            "force_invalid_json": True,
        },
    )
    assert response.status_code == 422, response.text
    detail = response.json()["detail"]
    assert "will not invent" in detail["message"].lower()
    assert any("invalid JSON" in item for item in detail["details"])


def test_force_low_semantic_pauses_without_grant(api_client: TestClient) -> None:
    intent_id = _active(api_client)
    response = api_client.post(
        f"/v1/intents/{intent_id}/run",
        json={"inject": "low_semantic"},
    )
    assert response.status_code == 200, response.text
    evaluation = response.json()["evaluation"]
    assert evaluation["semantic"]["semantic_match"] == 0.61
    assert evaluation["decision"]["verdict"] == "PAUSE"
    assert evaluation["grant"] is None
    pay = api_client.post(
        "/v1/payments",
        json={"amount": evaluation["proposal"]["amount"], "currency": "INR", "idempotency_key": "idem-low-sem-01"},
    )
    assert pay.status_code == 403


def test_inject_poison_blocks_without_pay(api_client: TestClient) -> None:
    intent_id = _active(api_client)
    response = api_client.post(
        f"/v1/intents/{intent_id}/run",
        json={"inject": "poison"},
    )
    assert response.status_code == 200, response.text
    evaluation = response.json()["evaluation"]
    assert evaluation["proposal"]["product"]["id"] == "sku_poison_deal"
    assert evaluation["risk"]["injection_high"] is True
    assert evaluation["decision"]["verdict"] == "BLOCK"
    assert evaluation["grant"] is None
    pay = api_client.post(
        "/v1/payments",
        json={"amount": evaluation["proposal"]["amount"], "currency": "INR", "idempotency_key": "idem-poison-01"},
    )
    assert pay.status_code == 403


def test_force_agent_fail_records_audit(api_client: TestClient) -> None:
    intent_id = _active(api_client)
    response = api_client.post(
        f"/v1/intents/{intent_id}/run",
        json={"force_agent_fail": True},
    )
    assert response.status_code == 422, response.text
    events = api_client.get(f"/v1/intents/{intent_id}/activity").json()
    types = [item["event_type"] for item in events]
    assert "agent_failed" in types
    assert "proposal_submitted" not in types
    decision = api_client.get(f"/v1/intents/{intent_id}/decision")
    assert decision.status_code == 404


def test_force_timeout_then_reconcile_does_not_double_charge(api_client: TestClient) -> None:
    intent_id = _active(api_client)
    run = api_client.post(f"/v1/intents/{intent_id}/run")
    assert run.status_code == 200, run.text
    evaluation = run.json()["evaluation"]
    token = evaluation["grant"]["token"]
    created = api_client.post(
        "/v1/payments",
        json={
            "grant_token": token,
            "amount": evaluation["proposal"]["amount"],
            "currency": "INR",
            "idempotency_key": "idem-eval-timeout-01",
            "force_timeout": True,
        },
    )
    assert created.status_code == 200, created.text
    assert created.json()["status"] == "unknown"
    assert get_ledger().succeeded_count() == 0
    reconciled = api_client.get(f"/v1/payments/{created.json()['id']}")
    assert reconciled.json()["status"] == "succeeded"
    assert get_ledger().succeeded_count() == 1
    again = api_client.get(f"/v1/payments/{created.json()['id']}")
    assert again.json()["status"] == "succeeded"
    assert get_ledger().succeeded_count() == 1
