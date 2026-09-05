"""Agent tools. Untrusted page text is data, not instructions."""

from __future__ import annotations

from packages.commerce_agent.catalog import CATALOG, PAGES, CatalogProduct, get_by_id

MAX_TOOL_CALLS = 8


class ToolBudget:
    def __init__(self, limit: int = MAX_TOOL_CALLS) -> None:
        self.limit = limit
        self.calls = 0
        self.steps: list[dict[str, str]] = []

    def _use(self, tool: str, detail: str) -> None:
        if self.calls >= self.limit:
            raise AgentToolLimit(f"Tool limit of {self.limit} reached")
        self.calls += 1
        self.steps.append({"tool": tool, "detail": detail})

    def search_catalog(self, query: str, category: str | None = None) -> list[CatalogProduct]:
        self._use(
            "search_catalog",
            f"Searching catalog for {query}" + (f" in {category}" if category else ""),
        )
        needles = _tokens(query)
        if category:
            needles.update(_tokens(category))
        scored: list[tuple[int, CatalogProduct]] = []
        for item in CATALOG:
            haystack = _tokens(" ".join([item.name, item.category, " ".join(item.tags), item.brand or ""]))
            overlap = len(needles & haystack)
            if category and category.casefold() not in item.category.casefold() and item.category.casefold() not in category.casefold():
                if overlap == 0:
                    continue
                overlap = max(overlap - 2, 0)
            if overlap == 0:
                continue
            scored.append((overlap, item))
        scored.sort(key=lambda pair: (-pair[0], pair[1].amount))
        return [item for _, item in scored]

    def get_product(self, sku: str) -> CatalogProduct | None:
        item = get_by_id(sku)
        self._use("get_product", f"Inspecting {item.name if item else sku}")
        return item

    def read_page_fixture(self, sku: str) -> str | None:
        page = PAGES.get(sku)
        label = sku if page is None else f"Reading product page {sku}"
        self._use("read_page_fixture", label)
        return page


class AgentToolLimit(Exception):
    pass


def _tokens(text: str) -> set[str]:
    stop = {
        "buy",
        "me",
        "a",
        "an",
        "the",
        "for",
        "under",
        "and",
        "or",
        "with",
        "preferably",
        "please",
    }
    return {part for part in "".join(ch.lower() if ch.isalnum() else " " for ch in text).split() if part and part not in stop and not part.isdigit()}
