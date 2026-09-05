"""Catalog-backed commerce agent. Must not import a payment client."""

from __future__ import annotations

from packages.commerce_agent.catalog import CatalogProduct
from packages.commerce_agent.tools import MAX_TOOL_CALLS, AgentToolLimit, ToolBudget
from packages.intent_compiler.schemas import IntentContract
from packages.verification_engine.risk import INJECTION_PHRASES
from packages.verification_engine.schemas import ProductRef, ProposedAction

GENERIC_NAME_TOKENS = {
    "laptop",
    "laptops",
    "programming",
    "headphones",
    "wireless",
    "burger",
    "food",
    "flight",
    "flights",
    "direct",
    "morning",
    "vegetarian",
}


class AgentFailed(Exception):
    def __init__(self, message: str = "The agent could not propose a purchase") -> None:
        super().__init__(message)
        self.message = message


def run_agent(
    contract: IntentContract,
    *,
    tools: ToolBudget | None = None,
    query_suffix: str | None = None,
) -> tuple[ProposedAction, list[dict[str, str]]]:
    budget = tools or ToolBudget(MAX_TOOL_CALLS)
    query = contract.raw_request
    if query_suffix:
        query = f"{query} {query_suffix}"
    category = contract.hard_constraints.category
    try:
        hits = budget.search_catalog(query, category)
    except AgentToolLimit as exc:
        raise AgentFailed(str(exc)) from exc
    if not hits:
        raise AgentFailed("Catalog search returned no products.")

    inspected: list[tuple[CatalogProduct, str | None]] = []
    try:
        for item in hits[:2]:
            product = budget.get_product(item.id)
            if product is None:
                continue
            page = budget.read_page_fixture(item.id) if item.id in _page_skus() else None
            inspected.append((product, page))
    except AgentToolLimit as exc:
        if not inspected:
            raise AgentFailed(str(exc)) from exc

    if not inspected:
        inspected = [(hits[0], None)]

    chosen = _select(contract, query, inspected)
    if chosen is None:
        raise AgentFailed("No catalog item satisfied the authorized constraints.")

    product, page = chosen
    attributes = dict(product.attributes)
    if page:
        attributes["page_text"] = page
    proposal = ProposedAction(
        amount=product.amount,
        currency=contract.hard_constraints.currency.value,
        merchant=product.merchant,
        product=ProductRef(
            id=product.id,
            name=product.name,
            category=product.category,
            attributes=attributes,
        ),
        agent_rationale=_rationale(contract, product),
        scheduled_at=product.scheduled_at,
    )
    budget.steps.append(
        {
            "tool": "propose",
            "detail": f"Proposing {product.name} at {product.amount}",
        }
    )
    return proposal, budget.steps


def _page_skus() -> set[str]:
    from packages.commerce_agent.catalog import PAGES

    return set(PAGES)


def _select(
    contract: IntentContract,
    query: str,
    inspected: list[tuple[CatalogProduct, str | None]],
) -> tuple[CatalogProduct, str | None] | None:
    hard = contract.hard_constraints
    eligible: list[tuple[CatalogProduct, str | None]] = []
    for product, page in inspected:
        haystack = _haystack(product, page)
        if product.amount > hard.max_amount:
            continue
        if hard.category and not _category_ok(hard.category, product.category):
            continue
        if any(token.casefold() not in haystack for token in hard.must_include):
            continue
        if any(token.casefold() in haystack for token in hard.forbidden_attributes):
            continue
        eligible.append((product, page))

    if not eligible:
        return None

    targeted = [pair for pair in eligible if _is_named_in_query(query, pair[0])]
    pool = targeted or eligible
    clean = [pair for pair in pool if not _is_poisoned(pair[1])]
    if clean and not targeted:
        pool = clean
    elif clean and targeted and not _is_poisoned(targeted[0][1]):
        pool = clean

    brands = [brand.casefold() for brand in contract.preferences.preferred_brands if brand.strip()]
    if brands:
        branded = [pair for pair in pool if (pair[0].brand or "").casefold() in brands]
        if branded:
            pool = branded

    pool.sort(key=lambda pair: pair[0].amount)
    return pool[0]


def _is_named_in_query(query: str, product: CatalogProduct) -> bool:
    distinctive = [
        token
        for token in product.name.casefold().split()
        if token not in GENERIC_NAME_TOKENS and len(token) > 2
    ]
    if not distinctive:
        return False
    blob = query.casefold()
    return all(token in blob for token in distinctive[:2]) or any(token in blob for token in distinctive if token in {"ultra", "deal", "poison"})


def _is_poisoned(page: str | None) -> bool:
    if not page:
        return False
    blob = page.casefold()
    return any(phrase in blob for phrase in INJECTION_PHRASES)


def _category_ok(required: str, actual: str) -> bool:
    want = required.casefold().strip()
    got = actual.casefold().strip()
    return want == got or want in got or got in want


def _haystack(product: CatalogProduct, page: str | None) -> str:
    parts = [
        product.name,
        product.category,
        product.id,
        product.brand or "",
        " ".join(product.tags),
        " ".join(f"{key} {value}" for key, value in product.attributes.items()),
        page or "",
    ]
    return " ".join(parts).casefold()


def _rationale(contract: IntentContract, product: CatalogProduct) -> str:
    return (
        f"Selected {product.name} from the demo catalog within the authorized "
        f"maximum of {contract.hard_constraints.max_amount}."
    )
