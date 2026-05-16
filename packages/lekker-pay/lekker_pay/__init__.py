"""
Lekker Pay - Unified payment adapter library for South African payment providers.

This package provides a single interface for integrating with multiple SA payment
providers (PayFast, Ozow, Yoco) through a consistent API.

Example:
    from lekker_pay import PaymentRouter, PaymentIntent, ProviderConfig
    
    config = {
        "payfast": ProviderConfig(
            merchant_id="10000100",
            merchant_key="46f0cd694581a",
            passphrase="jt7NOE43FZPn",
            sandbox=True
        )
    }
    
    router = PaymentRouter(config)
    
    intent = PaymentIntent(
        amount_cents=10000,
        currency="ZAR",
        reference="ORDER-123",
        customer_email="customer@example.com",
        customer_name="John Doe",
        return_url="https://example.com/success",
        cancel_url="https://example.com/cancel",
        webhook_url="https://example.com/webhooks/payment"
    )
    
    result = await router.create_payment("payfast", intent)
"""

__version__ = "0.1.0"

from lekker_pay.base import (
    BasePaymentAdapter,
    PaymentIntent,
    PaymentResult,
    PaymentStatus,
    ProviderConfig,
    WebhookEvent,
)
from lekker_pay.errors import (
    AuthenticationError,
    InvalidRequestError,
    LekkerPayError,
    NetworkError,
    PaymentNotFoundError,
    ProviderError,
    RateLimitError,
    RefundError,
    SignatureMismatchError,
)
from lekker_pay.router import PaymentRouter
from lekker_pay.providers.payfast import PayFastAdapter, PayFastConfig

__all__ = [
    # Version
    "__version__",
    # Core classes
    "PaymentRouter",
    "BasePaymentAdapter",
    # Models
    "PaymentIntent",
    "PaymentResult",
    "PaymentStatus",
    "ProviderConfig",
    "WebhookEvent",
    # Providers
    "PayFastAdapter",
    "PayFastConfig",
    # Exceptions
    "LekkerPayError",
    "ProviderError",
    "AuthenticationError",
    "InvalidRequestError",
    "NetworkError",
    "SignatureMismatchError",
    "RateLimitError",
    "PaymentNotFoundError",
    "RefundError",
]

# Made with Bob
