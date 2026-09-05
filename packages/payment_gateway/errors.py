class GrantError(Exception):
    def __init__(self, message: str = "Payment requires a valid unused authorization grant") -> None:
        super().__init__(message)
        self.message = message


class GrantRequired(GrantError):
    pass


class GrantInvalid(GrantError):
    pass


class GrantMismatch(GrantError):
    def __init__(self, message: str = "Grant does not match this payment") -> None:
        super().__init__(message)


class ProviderTimeout(Exception):
    def __init__(self, provider_ref: str | None = None) -> None:
        super().__init__("Payment provider timed out")
        self.provider_ref = provider_ref


class CheckoutError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
