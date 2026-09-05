from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from inspect import getsource
from uuid import uuid4

import pytest

from packages.intent_compiler.schemas import HardConstraints, IntentContract
from packages.verification_engine import constraint_checker
from packages.verification_engine.constraint_checker import check_constraints
from packages.verification_engine.schemas import ProductRef, ProposedAction


def _contract(**overrides: object) -> IntentContract:
    now = datetime.now(timezone.utc)
    payload = {
        "intent_id": uuid4(),
        "raw_request": "Buy a programming laptop under 60000",
        "goal": "Buy a programming laptop",
        "hard_constraints": HardConstraints(
            max_amount=Decimal("60000"),
            currency="INR",
            category="laptop",
        ),
        "expires_at": now + timedelta(hours=1),
        "created_at": now,
    }
    payload.update(overrides)
    if isinstance(payload["hard_constraints"], dict):
        payload["hard_constraints"] = HardConstraints.model_validate(payload["hard_constraints"])
    return IntentContract.model_validate(payload)


def _proposal(amount: int | Decimal, **overrides: object) -> ProposedAction:
    payload = {
        "amount": amount,
        "merchant": "demo_catalog",
        "product": ProductRef(id="sku_laptop", name="Programming laptop", category="laptop"),
    }
    payload.update(overrides)
    return ProposedAction.model_validate(payload)


def test_constraint_checker_does_not_import_llm() -> None:
    source = getsource(constraint_checker)
    assert "gemini" not in source.lower()
    assert "genai" not in source.lower()
    assert "openai" not in source.lower()


@pytest.mark.parametrize(
    ("amount", "should_pass"),
    [
        (58000, True),
        (60000, True),
        (85000, False),
    ],
)
def test_budget_table(amount: int, should_pass: bool) -> None:
    result = check_constraints(_contract(), _proposal(amount))
    assert result.passed is should_pass
    codes = [item.code for item in result.failures]
    if should_pass:
        assert "budget_exceeded" not in codes
    else:
        assert "budget_exceeded" in codes


def test_currency_mismatch() -> None:
    result = check_constraints(_contract(), _proposal(58000, currency="USD"))
    assert not result.passed
    assert result.failures[0].code == "currency_mismatch"


def test_quantity_exceeded() -> None:
    result = check_constraints(_contract(), _proposal(58000, quantity=2))
    assert not result.passed
    assert any(item.code == "quantity_exceeded" for item in result.failures)


def test_category_mismatch() -> None:
    result = check_constraints(
        _contract(),
        _proposal(58000, product=ProductRef(id="sku_phone", name="Phone", category="phone")),
    )
    assert not result.passed
    assert any(item.code == "category_mismatch" for item in result.failures)


def test_merchant_allowlist() -> None:
    contract = _contract(
        hard_constraints=HardConstraints(
            max_amount=Decimal("60000"),
            currency="INR",
            category="laptop",
            allowed_merchants=["demo_catalog"],
        )
    )
    ok = check_constraints(contract, _proposal(58000, merchant="demo_catalog"))
    blocked = check_constraints(contract, _proposal(58000, merchant="other_store"))
    assert ok.passed
    assert not blocked.passed
    assert any(item.code == "merchant_not_allowed" for item in blocked.failures)


def test_must_include_and_forbidden() -> None:
    contract = _contract(
        hard_constraints=HardConstraints(
            max_amount=Decimal("60000"),
            currency="INR",
            category="laptop",
            must_include=["direct"],
            forbidden_attributes=["gaming"],
        )
    )
    missing = check_constraints(contract, _proposal(58000))
    forbidden = check_constraints(
        contract,
        _proposal(
            58000,
            product=ProductRef(
                id="sku_game",
                name="Direct gaming laptop",
                category="laptop",
            ),
        ),
    )
    assert any(item.code == "missing_required_attribute" for item in missing.failures)
    assert any(item.code == "forbidden_attribute" for item in forbidden.failures)


def test_expired_authorization() -> None:
    past = datetime.now(timezone.utc) - timedelta(minutes=1)
    result = check_constraints(_contract(expires_at=past), _proposal(58000), now=datetime.now(timezone.utc))
    assert not result.passed
    assert any(item.code == "authorization_expired" for item in result.failures)


def test_duplicate_fingerprint() -> None:
    contract = _contract()
    proposal = _proposal(58000)
    from packages.verification_engine.fingerprint import proposal_fingerprint

    fingerprint = proposal_fingerprint(contract.intent_id, proposal)
    first = check_constraints(contract, proposal, existing_fingerprints=set())
    second = check_constraints(contract, proposal, existing_fingerprints={fingerprint})
    assert first.passed
    assert not second.passed
    assert any(item.code == "duplicate_transaction" for item in second.failures)


def test_morning_time_window() -> None:
    contract = _contract(
        hard_constraints=HardConstraints(
            max_amount=Decimal("8000"),
            currency="INR",
            category="flight",
            time_window="morning",
        )
    )
    morning = _proposal(
        7500,
        product=ProductRef(id="6e-101", name="IndiGo 6E-101", category="flight"),
        scheduled_at=datetime(2026, 9, 5, 8, 0, tzinfo=timezone.utc),
    )
    evening = morning.model_copy(
        update={"scheduled_at": datetime(2026, 9, 5, 19, 0, tzinfo=timezone.utc)}
    )
    assert check_constraints(contract, morning).passed
    assert not check_constraints(contract, evening).passed
