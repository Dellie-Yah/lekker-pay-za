"""
Unified exception hierarchy for Lekker Pay.

All provider-specific errors must be caught and re-raised as one of these exceptions.
Never let raw httpx.HTTPError or provider-specific exceptions escape the adapter boundary.
"""


class LekkerPayError(Exception):
    """Base exception for all Lekker Pay errors."""

    def __init__(self, message: str, provider: str | None = None) -> None:
        self.message = message
        self.provider = provider
        super().__init__(message)


class ProviderError(LekkerPayError):
    """Base class for provider-specific errors."""

    pass


class AuthenticationError(ProviderError):
    """
    Raised when provider authentication fails.
    
    Examples:
    - Invalid API key
    - Invalid merchant ID
    - Expired credentials
    """

    pass


class InvalidRequestError(ProviderError):
    """
    Raised when the request to the provider is invalid.
    
    Examples:
    - Missing required fields
    - Invalid amount format
    - Unsupported currency
    - Provider doesn't support partial refunds
    """

    pass


class NetworkError(ProviderError):
    """
    Raised when network communication with the provider fails.
    
    Examples:
    - Connection timeout
    - DNS resolution failure
    - Provider service unavailable
    """

    pass


class SignatureMismatchError(ProviderError):
    """
    Raised when webhook signature verification fails.
    
    CRITICAL: This must use constant-time comparison (hmac.compare_digest).
    Never use == to compare signatures.
    """

    pass


class RateLimitError(ProviderError):
    """
    Raised when provider rate limit is exceeded.
    
    Should include retry-after information if available.
    """

    def __init__(
        self,
        message: str,
        provider: str | None = None,
        retry_after_seconds: int | None = None,
    ) -> None:
        super().__init__(message, provider)
        self.retry_after_seconds = retry_after_seconds


class PaymentNotFoundError(ProviderError):
    """
    Raised when attempting to query or refund a payment that doesn't exist.
    """

    pass


class RefundError(ProviderError):
    """
    Raised when a refund operation fails.
    
    Examples:
    - Payment not in refundable state
    - Refund amount exceeds original payment
    - Provider-specific refund restrictions
    """

    pass

# Made with Bob
