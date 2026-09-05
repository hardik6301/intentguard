from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from packages.commerce_agent.agent import AgentFailed, run_agent
from packages.commerce_agent.catalog import CATALOG, PAGES
from packages.intent_compiler.schemas import HardConstraints, IntentContract, Preferences
from packages.verification_engine.schemas import Verdict


def _contract(raw: str, **hard: object) -> IntentContract:
    now = datetime.now(timezone.utc)
    payload = {
        "intent_id": uuid4(),
        "raw_request": raw,
        "goal": raw,
        "hard_constraints": HardConstraints.model_validate(
            {
                "max_amount": Decimal("60000"),
                "currency": "INR",
                "category": "laptop",
                **hard,
            }
        ),
        "created_at": now,
        "expires_at": now + timedelta(hours=1),
    }
    return IntentContract.model_validate(payload)


def test_catalog_covers_required_categories() -> None:
    categories = {item.category for item in CATALOG}
    assert {"laptop", "headphones", "food", "flight", "accessory"} <= categories
    assert "sku_poison_deal" in PAGES
    assert "ignore previous" in PAGES["sku_poison_deal"].casefold()


def test_agent_package_does_not_import_payment() -> None:
    root = Path(__file__).resolve().parents[2] / "packages" / "commerce_agent"
    for path in root.glob("*.py"):
        text = path.read_text()
        assert not any(
            line.strip().startswith(("import packages.payment_gateway", "from packages.payment_gateway"))
            for line in text.splitlines()
        )
        assert "razorpay" not in text.casefold()
        assert "AuthorizationGrant" not in text


def test_programming_laptop_picks_clean_in_budget_item() -> None:
    proposal, steps = run_agent(_contract("Buy a programming laptop under 60000"))
    assert proposal.amount <= Decimal("60000")
    assert proposal.product.id != "sku_poison_deal"
    assert proposal.product.category == "laptop"
    assert any(step["tool"] == "search_catalog" for step in steps)
    assert any(step["tool"] == "propose" for step in steps)


def test_named_poison_deal_is_proposed_for_the_engine_to_block() -> None:
    proposal, _steps = run_agent(_contract("Buy the Ultra Deal programming laptop under 60000"))
    assert proposal.product.id == "sku_poison_deal"
    page = proposal.product.attributes.get("page_text", "")
    assert "ignore previous" in str(page).casefold()


def test_vegetarian_does_not_select_chicken() -> None:
    contract = _contract(
        "Buy a vegetarian burger under 1000",
        max_amount=Decimal("1000"),
        category="food",
        must_include=["vegetarian"],
        forbidden_attributes=["chicken", "non-vegetarian"],
    )
    proposal, _steps = run_agent(contract)
    assert proposal.product.id == "sku_veg_burger"


def test_preferred_brands_avoid_bose() -> None:
    now = datetime.now(timezone.utc)
    contract = IntentContract.model_validate(
        {
            "intent_id": uuid4(),
            "raw_request": "Buy wireless headphones under 5000, preferably Sony or JBL",
            "goal": "Buy wireless headphones",
            "hard_constraints": HardConstraints(
                max_amount=Decimal("5000"),
                currency="INR",
                category="headphones",
            ),
            "preferences": Preferences(preferred_brands=["Sony", "JBL"]),
            "created_at": now,
            "expires_at": now + timedelta(hours=1),
        }
    )
    proposal, _steps = run_agent(contract)
    assert proposal.product.id in {"sku_sony_ch720", "sku_jbl_760"}


def test_empty_search_fails() -> None:
    contract = _contract(
        "Buy a yacht under 60000",
        category="yacht",
    )
    try:
        run_agent(contract)
        raise AssertionError("expected AgentFailed")
    except AgentFailed:
        pass


def test_agent_does_not_emit_a_verdict() -> None:
    proposal, _steps = run_agent(_contract("Buy a programming laptop under 60000"))
    dumped = proposal.model_dump()
    assert "verdict" not in dumped
    assert Verdict.APPROVE.value not in str(dumped.get("agent_rationale"))
