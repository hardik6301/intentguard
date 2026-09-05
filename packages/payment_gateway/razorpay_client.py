"""Razorpay Test Mode. Grant-gated. Never imported by the commerce agent."""

from __future__ import annotations

import hmac
import json
import urllib.error
import urllib.request
from base64 import b64encode
from hashlib import sha256
from typing import Any, Protocol

from packages.payment_gateway.errors import ProviderTimeout
from packages.payment_gateway.schemas import CheckoutSession


def amount_to_paise(amount: object) -> int:
    from decimal import Decimal

    return int((Decimal(str(amount)) * 100).quantize(Decimal("1")))


def payment_signature(order_id: str, payment_id: str, secret: str) -> str:
    payload = f"{order_id}|{payment_id}"
    return hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), sha256).hexdigest()


def webhook_signature(raw_body: bytes, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), raw_body, sha256).hexdigest()


class RazorpayOrder:
    def __init__(self, *, order_id: str, amount_paise: int, currency: str, status: str, receipt: str) -> None:
        self.order_id = order_id
        self.amount_paise = amount_paise
        self.currency = currency
        self.status = status
        self.receipt = receipt


class RazorpayGateway(Protocol):
    key_id: str
    secret: str

    def create_order(
        self,
        *,
        amount_paise: int,
        currency: str,
        receipt: str,
        notes: dict[str, str],
    ) -> RazorpayOrder: ...

    def fetch_order(self, order_id: str) -> RazorpayOrder | None: ...


class FakeRazorpay:
    """In-memory Test Mode stand-in. Used in pytest. Never talks to Razorpay."""

    def __init__(self, key_id: str = "rzp_test_intentguard", secret: str = "test_razorpay_secret") -> None:
        self.key_id = key_id
        self.secret = secret
        self.reset()

    def reset(self) -> None:
        self.orders: dict[str, RazorpayOrder] = {}
        self._by_receipt: dict[str, RazorpayOrder] = {}
        self._timeout_mode: str | None = None
        self.create_calls = 0

    def arm_timeout(self, *, committed: bool = False) -> None:
        self._timeout_mode = "committed" if committed else "empty"

    def create_order(
        self,
        *,
        amount_paise: int,
        currency: str,
        receipt: str,
        notes: dict[str, str],
    ) -> RazorpayOrder:
        self.create_calls += 1
        existing = self._by_receipt.get(receipt)
        if existing is not None and existing.status == "paid":
            return existing
        mode = self._timeout_mode
        self._timeout_mode = None
        if mode == "empty":
            raise ProviderTimeout(provider_ref=None)
        if existing is None:
            order = RazorpayOrder(
                order_id=f"order_{len(self.orders) + 1:04d}",
                amount_paise=amount_paise,
                currency=currency,
                status="created",
                receipt=receipt,
            )
            self.orders[order.order_id] = order
            self._by_receipt[receipt] = order
        else:
            order = existing
        if mode == "committed":
            raise ProviderTimeout(provider_ref=order.order_id)
        return order

    def fetch_order(self, order_id: str) -> RazorpayOrder | None:
        return self.orders.get(order_id)

    def mark_paid(self, order_id: str) -> RazorpayOrder:
        order = self.orders[order_id]
        order.status = "paid"
        return order

    def sign_checkout(self, order_id: str, payment_id: str) -> str:
        return payment_signature(order_id, payment_id, self.secret)

    def sign_webhook(self, raw_body: bytes) -> str:
        return webhook_signature(raw_body, self.secret)


class LiveRazorpay:
    def __init__(self, key_id: str, secret: str, *, timeout_seconds: float = 8.0) -> None:
        self.key_id = key_id
        self.secret = secret
        self.timeout_seconds = timeout_seconds

    def create_order(
        self,
        *,
        amount_paise: int,
        currency: str,
        receipt: str,
        notes: dict[str, str],
    ) -> RazorpayOrder:
        payload = {
            "amount": amount_paise,
            "currency": currency,
            "receipt": receipt[:40],
            "payment_capture": 1,
            "notes": notes,
        }
        data = self._request("POST", "https://api.razorpay.com/v1/orders", payload)
        return self._order_from_payload(data, receipt)

    def fetch_order(self, order_id: str) -> RazorpayOrder | None:
        try:
            data = self._request("GET", f"https://api.razorpay.com/v1/orders/{order_id}", None)
        except FileNotFoundError:
            return None
        return self._order_from_payload(data, str(data.get("receipt") or ""))

    def _order_from_payload(self, data: dict[str, Any], receipt: str) -> RazorpayOrder:
        status = str(data.get("status") or "created")
        if status == "paid":
            mapped = "paid"
        elif status == "attempted":
            mapped = "attempted"
        else:
            mapped = "created"
        return RazorpayOrder(
            order_id=str(data["id"]),
            amount_paise=int(data["amount"]),
            currency=str(data.get("currency") or "INR"),
            status=mapped,
            receipt=receipt,
        )

    def _request(self, method: str, url: str, payload: dict[str, Any] | None) -> dict[str, Any]:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        token = b64encode(f"{self.key_id}:{self.secret}".encode("utf-8")).decode("ascii")
        request = urllib.request.Request(
            url,
            data=body,
            method=method,
            headers={
                "Authorization": f"Basic {token}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except TimeoutError as exc:
            raise ProviderTimeout(provider_ref=None) from exc
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                raise FileNotFoundError(url) from exc
            raise
        except urllib.error.URLError as exc:
            raise ProviderTimeout(provider_ref=None) from exc


_OVERRIDE: RazorpayGateway | None = None
_FAKE = FakeRazorpay()


def set_razorpay_client(client: RazorpayGateway | None) -> None:
    global _OVERRIDE
    _OVERRIDE = client


def reset_razorpay() -> None:
    global _OVERRIDE
    _OVERRIDE = None
    _FAKE.reset()


def get_razorpay_client() -> RazorpayGateway | None:
    if _OVERRIDE is not None:
        return _OVERRIDE
    from apps.api.config import get_settings

    settings = get_settings()
    if settings.razorpay_key_id and settings.razorpay_key_secret:
        return LiveRazorpay(settings.razorpay_key_id, settings.razorpay_key_secret)
    return None


def checkout_session(client: RazorpayGateway, order: RazorpayOrder) -> CheckoutSession:
    return CheckoutSession(
        key_id=client.key_id,
        order_id=order.order_id,
        amount_paise=order.amount_paise,
        currency=order.currency,
        name="IntentGuard",
    )
