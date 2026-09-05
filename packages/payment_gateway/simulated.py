"""In-process simulated ledger. Default payment provider."""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

from packages.payment_gateway.errors import ProviderTimeout
from packages.payment_gateway.schemas import SimulatedCharge


class SimulatedLedger:
    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self._by_key: dict[str, SimulatedCharge] = {}
        self._by_ref: dict[str, SimulatedCharge] = {}
        self._timeout_mode: str | None = None

    def arm_timeout(self, *, committed: bool = False) -> None:
        self._timeout_mode = "committed" if committed else "empty"

    def create(
        self,
        *,
        amount: Decimal,
        currency: str,
        idempotency_key: str,
    ) -> SimulatedCharge:
        existing = self._by_key.get(idempotency_key)
        if existing is not None and existing.status == "succeeded":
            return existing
        mode = self._timeout_mode
        self._timeout_mode = None
        if mode == "empty":
            raise ProviderTimeout(provider_ref=None)
        if mode == "committed":
            charge = self._put(amount=amount, currency=currency, idempotency_key=idempotency_key)
            raise ProviderTimeout(provider_ref=charge.provider_ref)
        return self._put(amount=amount, currency=currency, idempotency_key=idempotency_key)

    def fetch(self, provider_ref: str | None) -> SimulatedCharge | None:
        if not provider_ref:
            return None
        return self._by_ref.get(provider_ref)

    def fetch_by_idempotency(self, idempotency_key: str) -> SimulatedCharge | None:
        return self._by_key.get(idempotency_key)

    def succeeded_count(self) -> int:
        return sum(1 for item in self._by_key.values() if item.status == "succeeded")

    def _put(self, *, amount: Decimal, currency: str, idempotency_key: str) -> SimulatedCharge:
        existing = self._by_key.get(idempotency_key)
        if existing is not None:
            return existing
        charge = SimulatedCharge(
            provider_ref=f"sim_{uuid4().hex[:16]}",
            idempotency_key=idempotency_key,
            amount=Decimal(amount),
            currency=currency,
            status="succeeded",
        )
        self._by_key[idempotency_key] = charge
        self._by_ref[charge.provider_ref] = charge
        return charge


_LEDGER = SimulatedLedger()


def get_ledger() -> SimulatedLedger:
    return _LEDGER


def reset_ledger() -> None:
    _LEDGER.reset()
