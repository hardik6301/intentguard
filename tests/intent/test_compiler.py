from decimal import Decimal

import pytest

from packages.intent_compiler.amounts import (
    MISSING_BUDGET_MESSAGE,
    UNGROUNDED_BUDGET_MESSAGE,
    budget_candidates,
    resolve_max_amount,
)
from packages.intent_compiler.compiler import IntentCompiler
from packages.intent_compiler.schemas import CompileFailed


class ScriptedLLM:
    def __init__(self, responses: list[str]) -> None:
        self.responses = list(responses)
        self.calls = 0

    def generate_json(self, prompt: str) -> str:
        self.calls += 1
        if not self.responses:
            raise AssertionError(f"unexpected LLM call for prompt: {prompt[:80]}")
        return self.responses.pop(0)


HEADPHONES_JSON = """
{
  "goal": "purchase wireless headphones",
  "hard_constraints": {
    "max_amount": 5000,
    "currency": "INR",
    "category": "wireless headphones",
    "quantity": 1
  },
  "preferences": {
    "preferred_brands": ["Sony", "JBL"]
  }
}
"""

INVENTED_BUDGET_JSON = """
{
  "goal": "buy something",
  "hard_constraints": {
    "max_amount": 5000,
    "currency": "INR",
    "category": "headphones"
  },
  "preferences": {}
}
"""


def test_budget_candidates_from_rupee_and_under() -> None:
    text = "Buy me wireless headphones for under ₹5,000, preferably Sony or JBL."
    assert budget_candidates(text) == [Decimal("5000")]


def test_five_thousand_words_are_not_candidates() -> None:
    assert budget_candidates("probably around five thousand") == []


def test_resolve_fills_single_explicit_amount_when_llm_omits() -> None:
    assert resolve_max_amount("Laptop under 60000", None) == Decimal("60000")


def test_resolve_rejects_ungrounded_invention() -> None:
    assert resolve_max_amount("probably around five thousand", Decimal("5000")) is None


def test_compile_headphones_extracts_amount_and_brands() -> None:
    compiler = IntentCompiler(llm=ScriptedLLM([HEADPHONES_JSON]))
    contract = compiler.compile(
        "Buy me wireless headphones for under ₹5000, preferably Sony or JBL."
    )
    assert contract.hard_constraints.max_amount == Decimal("5000")
    assert contract.preferences.preferred_brands == ["Sony", "JBL"]
    assert contract.hard_constraints.category == "wireless headphones"


def test_compile_does_not_invent_budget_from_words() -> None:
    compiler = IntentCompiler(llm=ScriptedLLM([INVENTED_BUDGET_JSON]))
    with pytest.raises(CompileFailed) as caught:
        compiler.compile("probably around five thousand")
    assert caught.value.message == UNGROUNDED_BUDGET_MESSAGE


def test_compile_retries_invalid_json_then_succeeds() -> None:
    compiler = IntentCompiler(llm=ScriptedLLM(["not-json", HEADPHONES_JSON]))
    contract = compiler.compile("Buy wireless headphones under ₹5000, preferably Sony or JBL.")
    assert contract.hard_constraints.max_amount == Decimal("5000")
    assert compiler.llm.calls == 2


def test_heuristic_client_headphones() -> None:
    from packages.intent_compiler.heuristic_client import HeuristicJsonClient

    compiler = IntentCompiler(llm=HeuristicJsonClient())
    contract = compiler.compile(
        "Buy me wireless headphones for under ₹5000, preferably Sony or JBL."
    )
    assert contract.hard_constraints.max_amount == Decimal("5000")
    assert "Sony" in contract.preferences.preferred_brands
    assert "JBL" in contract.preferences.preferred_brands


def test_compile_fails_after_retry_without_guessing() -> None:
    compiler = IntentCompiler(
        llm=ScriptedLLM(
            [
                '{"budget": "probably around five thousand"}',
                '{"hard_constraints": {"max_amount": "probably around five thousand"}}',
            ]
        )
    )
    with pytest.raises(CompileFailed) as caught:
        compiler.compile("probably around five thousand")
    assert MISSING_BUDGET_MESSAGE in caught.value.message
