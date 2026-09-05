from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from typing import Any
from uuid import UUID

from packages.intent_compiler.schemas import IntentContract


def _canonicalize(value: Any) -> Any:
    if isinstance(value, Decimal):
        if value == value.to_integral_value():
            return int(value)
        return float(value)
    if isinstance(value, UUID):
        return str(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _canonicalize(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [_canonicalize(item) for item in value]
    return value


def canonical_contract_payload(contract: IntentContract) -> dict[str, Any]:
    dumped = contract.model_dump(mode="python", exclude={"status"})
    return _canonicalize(dumped)


def canonical_contract_json(contract: IntentContract) -> str:
    return json.dumps(canonical_contract_payload(contract), separators=(",", ":"), ensure_ascii=True)


def contract_hash(contract: IntentContract) -> str:
    return hashlib.sha256(canonical_contract_json(contract).encode("utf-8")).hexdigest()
