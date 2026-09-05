from decimal import Decimal

import pytest

from packages.payment_gateway.errors import GrantRequired
from packages.payment_gateway.grants import authenticate_grant, verify_grant


def test_empty_token_is_required() -> None:
    with pytest.raises(GrantRequired):
        authenticate_grant(
            None,  # type: ignore[arg-type]
            token="",
            amount=Decimal("54990.00"),
            currency="INR",
            secret="test-secret",
        )


def test_verify_grant_requires_unused() -> None:
    with pytest.raises(GrantRequired):
        verify_grant(
            None,  # type: ignore[arg-type]
            token="",
            amount=Decimal("1.00"),
            currency="INR",
            secret="test-secret",
        )
