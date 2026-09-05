from decimal import Decimal

import pytest
from pydantic import ValidationError

from packages.intent_compiler.schemas import HardConstraints, IntentContract
from packages.verification_engine.schemas import ProposedAction


def _valid_contract_payload() -> dict:
    return {
        "raw_request": "Buy a programming laptop under 60000",
        "goal": "Buy a programming laptop",
        "hard_constraints": {
            "max_amount": 60000,
            "currency": "INR",
            "category": "laptop",
        },
    }


def test_intent_contract_accepts_numeric_max_amount() -> None:
    contract = IntentContract.model_validate(_valid_contract_payload())
    assert contract.hard_constraints.max_amount == Decimal("60000")


def test_intent_contract_rejects_string_max_amount() -> None:
    payload = _valid_contract_payload()
    payload["hard_constraints"]["max_amount"] = "60000"
    with pytest.raises(ValidationError):
        IntentContract.model_validate(payload)


def test_intent_contract_rejects_prose_budget() -> None:
    payload = _valid_contract_payload()
    payload["hard_constraints"]["max_amount"] = "around five thousand"
    with pytest.raises(ValidationError):
        IntentContract.model_validate(payload)


def test_hard_constraints_reject_string_amount_directly() -> None:
    with pytest.raises(ValidationError):
        HardConstraints.model_validate({"max_amount": "5000", "currency": "INR"})


def test_proposed_action_rejects_string_amount() -> None:
    with pytest.raises(ValidationError):
        ProposedAction.model_validate(
            {
                "amount": "58000",
                "merchant": "demo_catalog",
                "product": {"id": "sku_1", "name": "Laptop"},
            }
        )


def test_proposed_action_accepts_numeric_amount() -> None:
    action = ProposedAction.model_validate(
        {
            "amount": 58000,
            "merchant": "demo_catalog",
            "product": {"id": "sku_1", "name": "Laptop"},
        }
    )
    assert action.amount == Decimal("58000")
