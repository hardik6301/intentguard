from __future__ import annotations

import json
import re

from packages.intent_compiler.amounts import resolve_max_amount

KNOWN_BRANDS = ("Sony", "JBL", "Bose", "Apple", "Samsung", "ASUS", "Dell", "HP", "Lenovo")

CATEGORY_HINTS = (
    ("wireless headphone", "wireless headphones"),
    ("headphone", "headphones"),
    ("laptop", "laptop"),
    ("flight", "flight"),
    ("burger", "food"),
)


def _user_text(prompt: str) -> str:
    if "User request:" in prompt:
        return prompt.rsplit("User request:", 1)[-1].strip()
    return prompt.strip()


def _brands(text: str) -> list[str]:
    found: list[str] = []
    for brand in KNOWN_BRANDS:
        if re.search(rf"\b{re.escape(brand)}\b", text, flags=re.IGNORECASE):
            found.append(brand)
    return found


def _category(text: str) -> str | None:
    lowered = text.lower()
    for needle, label in CATEGORY_HINTS:
        if needle in lowered:
            return label
    return None


class HeuristicJsonClient:
    """Local stand-in used only when GEMINI_API_KEY is unset. Still cannot invent budgets."""

    def generate_json(self, prompt: str) -> str:
        raw = _user_text(prompt)
        amount = resolve_max_amount(raw, None)
        weight = "lightweight" if "lightweight" in raw.lower() else None
        use_case = "programming" if "programming" in raw.lower() else None
        payload = {
            "goal": raw[:160],
            "hard_constraints": {
                "max_amount": float(amount) if amount is not None else None,
                "currency": "INR",
                "category": _category(raw),
                "quantity": 1,
            },
            "preferences": {
                "preferred_brands": _brands(raw),
                "weight": weight,
                "use_case": use_case,
            },
        }
        return json.dumps(payload)
