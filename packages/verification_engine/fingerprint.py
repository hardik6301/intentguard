from __future__ import annotations

import hashlib
from decimal import Decimal
from uuid import UUID

from packages.verification_engine.schemas import ProposedAction


def proposal_fingerprint(intent_id: UUID, proposal: ProposedAction) -> str:
    amount = format(Decimal(proposal.amount).quantize(Decimal("0.01")), "f")
    sku = proposal.product.id.strip().lower()
    merchant = proposal.merchant.strip().lower()
    payload = f"{intent_id}|{amount}|{sku}|{merchant}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
