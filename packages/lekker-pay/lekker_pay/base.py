"""
Base interface contract for all payment adapters.

This module defines the abstract base class and Pydantic models that all
provider adapters must implement. The interface is designed to be:
- Provider-agnostic
- Type-safe (mypy --strict compliant)
- Money-safe (always integers, never floats)
- Security-conscious (constant-time signature comparison)
"""

from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Any, ClassVar, Literal, Mapping

from pydantic import BaseModel, EmailStr, Field, HttpUrl


class PaymentStatus(str, Enum):
    """
    Unified payment status across all providers.
    
    Adapters must map provider-specific statuses to these values.
    """

    PENDING = "pending"  # Payment initiated but not yet processing
    PROCESSING = "processing"  # Payment actively being processed by provider
    SUCCEEDED = "succeeded"  # Payment completed successfully
    FAILED = "failed"  # Payment failed (insufficient funds, declined, etc.)
    REFUNDED = "refunded"  # Payment was refunded (full or partial)
    CANCELLED = "cancelled"  # Payment was cancelled before completion


class ProviderConfig(BaseModel):
    """
    Generic provider configuration.
    
    Each provider uses only the fields it needs. Adapters are stateless
    and receive config via constructor - no environment variable reads
    inside adapter classes.
    
    Example:
        PayFast uses: merchant_id, merchant_key, passphrase, sandbox
        Yoco uses: api_key, webhook_secret, sandbox
        Ozow uses: api_key, site_code, private_key, sandbox
    """

    api_key: str | None = None
    api_secret: str | None = None
    merchant_id: str | None = None
    merchant_key: str | None = None
    site_code: str | None = None
    private_key: str | None = None
    passphrase: str | None = None
    webhook_secret: str | None = None
    sandbox: bool = True
    base_url: str | None = None  # Override for testing


class PaymentIntent(BaseModel):
    """
    Provider-agnostic payment request.
    
    CRITICAL: amount_cents is always an integer. Never use floats for money.
    To represent R100.00, use amount_cents=10000.
    
    Example:
        intent = PaymentIntent(
            amount_cents=10000,  # R100.00
            currency="ZAR",
            reference="ORDER-123",
            customer_email="customer@example.com",
            customer_name="John Doe",
            return_url="https://example.com/success",
            cancel_url="https://example.com/cancel",
            webhook_url="https://example.com/webhooks/payment"
        )
    """

    amount_cents: int = Field(..., gt=0, description="Amount in cents (e.g., 10000 = R100.00)")
    currency: Literal["ZAR"] = Field(default="ZAR", description="Currency code (ZAR only for v1)")
    reference: str = Field(
        ..., min_length=1, max_length=100, description="Merchant-supplied idempotency key"
    )
    customer_email: EmailStr = Field(..., description="Customer email address")
    customer_name: str = Field(..., min_length=1, description="Customer full name")
    metadata: dict[str, str] = Field(
        default_factory=dict, description="Additional merchant data (max 10 keys)"
    )
    return_url: HttpUrl = Field(..., description="URL to redirect customer after success")
    cancel_url: HttpUrl = Field(..., description="URL to redirect customer after cancellation")
    webhook_url: HttpUrl = Field(..., description="URL to receive payment status webhooks")

    model_config = {"strict": True}


class PaymentResult(BaseModel):
    """
    Result of a payment operation (create or refund).
    
    Example:
        result = PaymentResult(
            provider="payfast",
            provider_payment_id="1234567",
            reference="ORDER-123",
            status=PaymentStatus.PENDING,
            redirect_url="https://sandbox.payfast.co.za/eng/process?id=abc123",
            raw={"m_payment_id": "1234567", "status": "PENDING"}
        )
    """

    provider: str = Field(..., description="Provider name (e.g., 'payfast')")
    provider_payment_id: str = Field(..., description="Provider's internal payment ID")
    reference: str = Field(..., description="Echoed from PaymentIntent")
    status: PaymentStatus = Field(..., description="Current payment status")
    redirect_url: HttpUrl | None = Field(
        None, description="URL to redirect customer (for redirect-based flows)"
    )
    raw: dict[str, Any] = Field(
        ..., description="Provider's untouched response for debugging (nested JSON allowed)"
    )

    model_config = {"strict": True}


class WebhookEvent(BaseModel):
    """
    Parsed and verified webhook event from a provider.
    
    This is returned by verify_webhook() after signature verification passes.
    
    Example:
        event = WebhookEvent(
            provider="payfast",
            event_type="payment.succeeded",
            provider_payment_id="1234567",
            reference="ORDER-123",
            amount_cents=10000,
            raw={"m_payment_id": "1234567", "payment_status": "COMPLETE"},
            received_at=datetime.now(timezone.utc)
        )
    """

    provider: str = Field(..., description="Provider name")
    event_type: Literal["payment.succeeded", "payment.failed", "payment.refunded"] = Field(
        ..., description="Normalized event type"
    )
    provider_payment_id: str = Field(..., description="Provider's payment ID")
    reference: str = Field(..., description="Merchant reference from original intent")
    amount_cents: int = Field(..., gt=0, description="Payment amount in cents")
    raw: dict[str, Any] = Field(
        ..., description="Provider's untouched webhook payload (nested JSON allowed)"
    )
    received_at: datetime = Field(..., description="When webhook was received (UTC)")

    model_config = {"strict": True}


class BasePaymentAdapter(ABC):
    """
    Abstract base class for all payment provider adapters.
    
    Adapters must be:
    - Stateless (config injected via constructor)
    - Type-safe (full type hints, mypy --strict compliant)
    - Money-safe (always use int cents, never floats)
    - Security-conscious (constant-time signature comparison)
    - Error-safe (catch all provider errors, re-raise as LekkerPayError subclasses)
    
    Example implementation:
        class PayFastAdapter(BasePaymentAdapter):
            provider_name = "payfast"
            
            def __init__(self, config: ProviderConfig) -> None:
                self.config = config
                self.client = httpx.AsyncClient(base_url=self._get_base_url())
            
            async def create_payment(self, intent: PaymentIntent) -> PaymentResult:
                # Implementation
                pass
    """

    provider_name: ClassVar[str]

    @abstractmethod
    def __init__(self, config: ProviderConfig) -> None:
        """
        Initialize adapter with provider configuration.
        
        Args:
            config: Provider-specific configuration (API keys, sandbox flag, etc.)
        """
        pass

    @abstractmethod
    async def create_payment(self, intent: PaymentIntent) -> PaymentResult:
        """
        Create a new payment with the provider.
        
        For redirect-based flows (PayFast, Ozow), this returns a redirect_url.
        For API-based flows (Yoco), this may initiate the payment directly.
        
        Args:
            intent: Provider-agnostic payment request
            
        Returns:
            PaymentResult with provider_payment_id and redirect_url (if applicable)
            
        Raises:
            AuthenticationError: Invalid credentials
            InvalidRequestError: Invalid payment parameters
            NetworkError: Provider communication failure
            
        Example:
            result = await adapter.create_payment(intent)
            # Redirect customer to result.redirect_url
        """
        pass

    @abstractmethod
    async def get_status(self, provider_payment_id: str) -> PaymentStatus:
        """
        Query current status of a payment.
        
        Args:
            provider_payment_id: Provider's internal payment ID
            
        Returns:
            Current PaymentStatus
            
        Raises:
            PaymentNotFoundError: Payment doesn't exist
            AuthenticationError: Invalid credentials
            NetworkError: Provider communication failure
            
        Example:
            status = await adapter.get_status("1234567")
            if status == PaymentStatus.SUCCEEDED:
                # Fulfill order
        """
        pass

    @abstractmethod
    def verify_webhook(self, headers: Mapping[str, str], body: bytes) -> WebhookEvent:
        """
        Verify webhook signature and parse event.
        
        CRITICAL SECURITY REQUIREMENTS:
        1. This method is SYNCHRONOUS (no async/await)
        2. Signature comparison MUST use hmac.compare_digest (constant-time)
        3. NEVER use == to compare signatures (timing attack vulnerability)
        4. Body must be raw bytes for signature verification (don't parse first)
        5. Raise SignatureMismatchError if verification fails
        
        Args:
            headers: HTTP headers from webhook request (case-insensitive mapping)
            body: Raw request body as bytes (not parsed JSON/form data)
            
        Returns:
            Parsed and verified WebhookEvent
            
        Raises:
            SignatureMismatchError: Signature verification failed
            InvalidRequestError: Malformed webhook payload
            
        Example:
            try:
                event = adapter.verify_webhook(request.headers, await request.body())
                # Process event (idempotency check in merchant-api layer)
            except SignatureMismatchError:
                # Log and return 401
                pass
        """
        pass

    @abstractmethod
    async def refund(
        self, provider_payment_id: str, amount_cents: int | None = None
    ) -> PaymentResult:
        """
        Refund a payment (full or partial).
        
        Args:
            provider_payment_id: Provider's internal payment ID
            amount_cents: Amount to refund in cents. If None, full refund.
            
        Returns:
            PaymentResult with status=REFUNDED
            
        Raises:
            PaymentNotFoundError: Payment doesn't exist
            RefundError: Payment not refundable or amount exceeds original
            InvalidRequestError: Provider doesn't support partial refunds
            AuthenticationError: Invalid credentials
            NetworkError: Provider communication failure
            
        Example:
            # Full refund
            result = await adapter.refund("1234567")
            
            # Partial refund (R50.00 of R100.00)
            result = await adapter.refund("1234567", amount_cents=5000)
        """
        pass

# Made with Bob
