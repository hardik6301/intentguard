from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apps.api.deps import get_compiler, get_db
from apps.api.main import app
from apps.api.models.db import Base
from packages.intent_compiler.amounts import MISSING_BUDGET_MESSAGE
from packages.intent_compiler.compiler import IntentCompiler
from tests.intent.test_compiler import HEADPHONES_JSON, INVENTED_BUDGET_JSON, ScriptedLLM


def _client(responses: list[str]) -> Generator[TestClient, None, None]:
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

    compiler = IntentCompiler(llm=ScriptedLLM(responses))
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_compiler] = lambda: compiler
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def headphones_client() -> Generator[TestClient, None, None]:
    yield from _client([HEADPHONES_JSON])


@pytest.fixture
def invented_client() -> Generator[TestClient, None, None]:
    yield from _client([INVENTED_BUDGET_JSON])


def test_compile_and_confirm_headphones(headphones_client: TestClient) -> None:
    compiled = headphones_client.post(
        "/v1/intents/compile",
        json={"raw_request": "Buy me wireless headphones for under ₹5000, preferably Sony or JBL."},
    )
    assert compiled.status_code == 200, compiled.text
    body = compiled.json()
    assert body["contract"]["hard_constraints"]["max_amount"] == 5000
    assert body["contract"]["preferences"]["preferred_brands"] == ["Sony", "JBL"]
    intent_id = body["intent_id"]

    confirmed = headphones_client.post("/v1/intents/", json={"intent_id": intent_id})
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["status"] == "active"

    fetched = headphones_client.get(f"/v1/intents/{intent_id}")
    assert fetched.status_code == 200
    assert fetched.json()["contract"]["hard_constraints"]["max_amount"] == 5000


def test_mutated_contract_on_confirm_is_conflict(headphones_client: TestClient) -> None:
    compiled = headphones_client.post(
        "/v1/intents/compile",
        json={"raw_request": "Buy wireless headphones under ₹5000, preferably Sony or JBL."},
    )
    body = compiled.json()
    mutated = body["contract"]
    mutated["hard_constraints"]["max_amount"] = 90000
    confirmed = headphones_client.post(
        "/v1/intents/",
        json={"intent_id": body["intent_id"], "contract": mutated},
    )
    assert confirmed.status_code == 409


def test_patch_intent_is_conflict(headphones_client: TestClient) -> None:
    compiled = headphones_client.post(
        "/v1/intents/compile",
        json={"raw_request": "Buy wireless headphones under ₹5000"},
    )
    intent_id = compiled.json()["intent_id"]
    patched = headphones_client.patch(
        f"/v1/intents/{intent_id}",
        json={"hard_constraints": {"max_amount": 90000}},
    )
    assert patched.status_code == 409


def test_compile_prose_budget_is_unprocessable(invented_client: TestClient) -> None:
    response = invented_client.post(
        "/v1/intents/compile",
        json={"raw_request": "probably around five thousand"},
    )
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert MISSING_BUDGET_MESSAGE in detail["message"] or "explicit numeral" in detail["message"]
