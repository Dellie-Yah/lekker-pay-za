"""
Paystack payment adapter for Lekker Pay.

Paystack is a pan-African payment gateway supporting Nigeria, Ghana, Kenya,
South Africa, and Côte d'Ivoire. This adapter implements card payment processing
with webhook notifications.

CRITICAL SECURITY NOTES:
- Webhook signature uses HMAC-SHA512 over raw request body bytes
- The secret_key (config.api_key) serves TWO purposes:
  1. Bearer token for API authentication (Authorization: Bearer sk_test_...)
  2. HMAC key for webhook signature verification
  This duality is intentional but must be documented at each use site.
- All signature comparisons use hmac.compare_digest (constant-time)
- Money is always int cents internally
- Amount format varies by endpoint:
  * /transaction/initialize: STRING "10000"
  * /refund: INTEGER 10000
  * Webhook/verify responses: INTEGER 10000
"""

import hashlib
import hmac
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any, ClassVar

import httpx
import structlog

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
    NetworkError,
    PaymentNotFoundError,
    RefundError,
    SignatureMismatchError,
)

logger = structlog.get_logger()

# API base URL (same for sandbox and live - environment determined by key prefix)
_BASE_URL = "https://api.paystack.co"

# Status mapping: Paystack status → PaymentStatus
_PAYSTACK_STATUS_MAP = {
    "success": PaymentStatus.SUCCEEDED,
    "failed": PaymentStatus.FAILED,
    "abandoned": PaymentStatus.FAILED,  # Customer left, treat as failure
    "pending": PaymentStatus.PENDING,
}

# Event mapping: Paystack event → unified event_type
_PAYSTACK_EVENT_MAP = {
    "charge.success": "payment.succeeded",
    "charge.failed": "payment.failed",
    "refund.processed": "payment.refunded",
}


class PaystackAdapter(BasePaymentAdapter):
    """
    Paystack payment adapter.

    Paystack uses a REST API with Bearer token authentication and HMAC-SHA512
    webhook signatures. The payment flow is redirect-based: initialize returns
    an authorization_url where the customer completes payment.

    CRITICAL: The secret_key (config.api_key) is used for BOTH:
    1. Bearer token in Authorization header for API calls
    2. HMAC-SHA512 key for webhook signature verification

    Example:
        config = ProviderConfig(
            api_key="sk_test_YOUR_SECRET_KEY",
            sandbox=True,
        )
        adapter = PaystackAdapter(config)

        # Create payment (returns redirect URL)
        result = await adapter.create_payment(intent)
        # Redirect customer to result.redirect_url

        # Verify webhook (two-step pattern)
        event = adapter.verify_webhook(request.headers, await request.body())
        # Optionally confirm with server-side verification
        status = await adapter.verify_transaction(event.reference)
    """

    provider_name: ClassVar[str] = "paystack"

    def __init__(self, config: ProviderConfig) -> None:
        """
        Initialize Paystack adapter with configuration.

        Args:
            config: Provider configuration with api_key (secret key) and sandbox flag

        Raises:
            ValueError: If api_key is missing
        """
        if not config.api_key:
            raise ValueError("Paystack requires api_key (secret key)")

        self.config = config
        self.logger = logger.bind(provider="paystack", sandbox=config.sandbox)

        # Log the duality: api_key used for both Bearer auth AND webhook HMAC
        self.logger.info(
            "paystack_adapter_initialized",
            note="api_key used for both Bearer token and webhook HMAC-SHA512",
        )

        # HTTP client for async operations
        self.client = httpx.AsyncClient(
            base_url=config.base_url or _BASE_URL,
            timeout=30.0,
            headers={"User-Agent": "LekkerPay/0.1.0"},
        )

    def _get_headers(self) -> dict[str, str]:
        """
        Get HTTP headers for API requests.

        CRITICAL: Uses config.api_key as Bearer token for authentication.
        This is the same key used for webhook HMAC verification.

        Returns:
            Headers dict with Authorization and Content-Type
        """
        return {
            "Authorization": f"Bearer {self.config.api_key}",  # api_key as Bearer token
            "Content-Type": "application/json",
        }

    def _cents_to_string(self, cents: int) -> str:
        """
        Convert integer cents to string for /transaction/initialize.

        Paystack's initialize endpoint expects amount as a STRING, not an integer.
        This is different from the refund endpoint which uses integers.

        Args:
            cents: Amount in cents (e.g., 10000 for R100.00)

        Returns:
            String representation of cents (e.g., "10000")

        Raises:
            InvalidRequestError: If cents is negative

        Example:
            >>> _cents_to_string(10000)
            "10000"
            >>> _cents_to_string(8550)
            "8550"
        """
        if cents < 0:
            raise InvalidRequestError(
                f"Amount cannot be negative: {cents} cents", provider="paystack"
            )
        return str(cents)

    def _map_status(self, paystack_status: str) -> PaymentStatus:
        """
        Map Paystack status to unified PaymentStatus.

        Args:
            paystack_status: Paystack status string

        Returns:
            Unified PaymentStatus enum value

        Raises:
            InvalidRequestError: If status is unknown
        """
        status = _PAYSTACK_STATUS_MAP.get(paystack_status)
        if status is None:
            raise InvalidRequestError(
                f"Unknown Paystack status: {paystack_status}", provider="paystack"
            )
        return status

    def _map_event(self, paystack_event: str) -> str:
        """
        Map Paystack event to unified event_type.

        Args:
            paystack_event: Paystack event string (e.g., "charge.success")

        Returns:
            Unified event_type string (e.g., "payment.succeeded")

        Raises:
            InvalidRequestError: If event is unknown
        """
        event_type = _PAYSTACK_EVENT_MAP.get(paystack_event)
        if event_type is None:
            raise InvalidRequestError(
                f"Unknown Paystack event: {paystack_event}", provider="paystack"
            )
        return event_type

    async def create_payment(self, intent: PaymentIntent) -> PaymentResult:
        """
        Create a new payment with Paystack.

        Calls POST /transaction/initialize and returns the authorization_url
        where the customer should be redirected to complete payment.

        CRITICAL: Amount must be sent as a STRING, not an integer.

        Args:
            intent: Provider-agnostic payment request

        Returns:
            PaymentResult with redirect_url set to authorization_url

        Raises:
            AuthenticationError: Invalid API key (401)
            InvalidRequestError: Invalid payment parameters (400, 4xx)
            NetworkError: Provider communication failure (5xx, network errors)

        Example:
            result = await adapter.create_payment(intent)
            # Redirect customer to result.redirect_url
        """
        try:
            # Build request payload
            # CRITICAL: amount must be a STRING for initialize endpoint
            payload = {
                "email": intent.customer_email,
                "amount": self._cents_to_string(intent.amount_cents),  # STRING format
                "currency": intent.currency,
                "reference": intent.reference,
                "callback_url": str(intent.return_url),
                "metadata": {
                    "custom_fields": [
                        {
                            "display_name": "Customer Name",
                            "variable_name": "customer_name",
                            "value": intent.customer_name,
                        }
                    ],
                    **intent.metadata,
                },
            }

            self.logger.info(
                "paystack_create_payment",
                reference=intent.reference,
                amount_cents=intent.amount_cents,
            )

            response = await self.client.post(
                "/transaction/initialize",
                headers=self._get_headers(),
                json=payload,
            )

            # Handle error responses
            if response.status_code == 401:
                raise AuthenticationError(
                    "Invalid Paystack API key", provider="paystack"
                )
            elif 400 <= response.status_code < 500:
                error_data = response.json()
                raise InvalidRequestError(
                    f"Paystack API error: {error_data.get('message', 'Unknown error')}",
                    provider="paystack",
                )
            elif response.status_code >= 500:
                raise NetworkError(
                    f"Paystack server error: {response.status_code}",
                    provider="paystack",
                )

            response.raise_for_status()
            data = response.json()

            if not data.get("status"):
                raise InvalidRequestError(
                    f"Paystack API error: {data.get('message', 'Unknown error')}",
                    provider="paystack",
                )

            # Extract response data
            response_data = data["data"]
            authorization_url = response_data["authorization_url"]
            # CRITICAL: Use Paystack's reference field (merchant-supplied), not id
            # The merchant matches orders by reference, not Paystack's internal numeric id
            reference = response_data["reference"]

            self.logger.info(
                "paystack_payment_created",
                reference=reference,
                authorization_url=authorization_url,
            )

            # Flatten nested response for raw field (must be scalar values only)
            raw_flat = {
                "authorization_url": authorization_url,
                "access_code": response_data.get("access_code", ""),
                "reference": reference,
            }

            return PaymentResult(
                provider="paystack",
                provider_payment_id=reference,  # Use reference, not id
                reference=reference,
                status=PaymentStatus.PENDING,
                redirect_url=authorization_url,  # NOT access_code
                raw=raw_flat,
            )

        except httpx.HTTPError as e:
            self.logger.error("paystack_http_error", error=str(e))
            raise NetworkError(
                f"Failed to communicate with Paystack: {e}", provider="paystack"
            ) from e

    async def get_status(self, provider_payment_id: str) -> PaymentStatus:
        """
        Query current status of a payment.

        Calls GET /transaction/verify/:reference to get the current payment status.

        Args:
            provider_payment_id: Paystack reference (used as payment ID)

        Returns:
            Current PaymentStatus

        Raises:
            PaymentNotFoundError: Transaction doesn't exist (404)
            AuthenticationError: Invalid API key (401)
            NetworkError: Provider communication failure

        Example:
            status = await adapter.get_status("ORDER-ABC123")
            if status == PaymentStatus.SUCCEEDED:
                # Fulfill order
        """
        try:
            self.logger.info(
                "paystack_get_status", provider_payment_id=provider_payment_id
            )

            response = await self.client.get(
                f"/transaction/verify/{provider_payment_id}",
                headers=self._get_headers(),
            )

            if response.status_code == 404:
                raise PaymentNotFoundError(
                    f"Transaction not found: {provider_payment_id}",
                    provider="paystack",
                )
            elif response.status_code == 401:
                raise AuthenticationError(
                    "Invalid Paystack API key", provider="paystack"
                )
            elif response.status_code >= 500:
                raise NetworkError(
                    f"Paystack server error: {response.status_code}",
                    provider="paystack",
                )

            response.raise_for_status()
            data = response.json()

            if not data.get("status"):
                raise InvalidRequestError(
                    f"Paystack API error: {data.get('message', 'Unknown error')}",
                    provider="paystack",
                )

            # Extract status from response
            transaction_data = data["data"]
            paystack_status = transaction_data["status"]
            status = self._map_status(paystack_status)

            self.logger.info(
                "paystack_status_retrieved",
                provider_payment_id=provider_payment_id,
                status=status.value,
            )

            return status

        except httpx.HTTPError as e:
            self.logger.error("paystack_http_error", error=str(e))
            raise NetworkError(
                f"Failed to communicate with Paystack: {e}", provider="paystack"
            ) from e

    def verify_webhook(self, headers: Mapping[str, str], body: bytes) -> WebhookEvent:
        """
        Verify webhook signature and parse event.

        CRITICAL SECURITY REQUIREMENTS:
        1. This method is SYNCHRONOUS (no async/await)
        2. Signature comparison MUST use hmac.compare_digest (constant-time)
        3. NEVER use == to compare signatures (timing attack vulnerability)
        4. Body must be raw bytes for signature verification (don't parse first)
        5. Uses config.api_key as HMAC-SHA512 key (same key as Bearer token)

        Args:
            headers: HTTP headers from webhook request (case-insensitive mapping)
            body: Raw request body as bytes (not parsed JSON)

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
        # Extract signature from headers (case-insensitive)
        signature_header = None
        for key, value in headers.items():
            if key.lower() == "x-paystack-signature":
                signature_header = value
                break

        if not signature_header:
            raise SignatureMismatchError(
                "Missing x-paystack-signature header", provider="paystack"
            )

        # Compute expected signature using HMAC-SHA512
        # CRITICAL: Uses config.api_key as HMAC key (same key as Bearer token)
        # Type assertion: api_key is guaranteed non-None by __init__ validation
        assert self.config.api_key is not None
        expected_signature = hmac.new(
            self.config.api_key.encode("utf-8"),  # api_key as HMAC key
            body,
            hashlib.sha512,
        ).hexdigest()

        # CRITICAL: Use constant-time comparison to prevent timing attacks
        if not hmac.compare_digest(expected_signature, signature_header):
            self.logger.warning("paystack_signature_mismatch")
            raise SignatureMismatchError(
                "Webhook signature verification failed", provider="paystack"
            )

        # Log successful verification (without logging the signature itself)
        self.logger.info("paystack_webhook_verified")

        # Parse webhook payload
        try:
            payload = json.loads(body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            raise InvalidRequestError(
                f"Invalid webhook payload: {e}", provider="paystack"
            ) from e

        # Extract event data
        event = payload.get("event")
        if not event:
            raise InvalidRequestError(
                "Missing event field in webhook payload", provider="paystack"
            )

        event_type = self._map_event(event)
        data = payload.get("data", {})

        # CRITICAL: Use Paystack's reference field (merchant-supplied), not id
        # The merchant matches orders by reference, not Paystack's internal numeric id
        reference = data.get("reference")
        amount = data.get("amount")  # INTEGER in cents from webhook
        transaction_id = data.get("id")

        if not reference or amount is None:
            raise InvalidRequestError(
                "Missing required fields in webhook payload", provider="paystack"
            )

        self.logger.info(
            "paystack_webhook_parsed",
            event_type=event_type,
            reference=reference,
            amount_cents=amount,
            transaction_id=transaction_id,
        )

        # Flatten nested payload for raw field (must be scalar values only)
        raw_flat = {
            "event": event,
            "reference": reference,
            "amount": amount,
            "transaction_id": str(transaction_id) if transaction_id else "",
            "status": data.get("status", ""),
        }

        return WebhookEvent(
            provider="paystack",
            event_type=event_type,  # type: ignore
            provider_payment_id=reference,  # Use reference, not id
            reference=reference,
            amount_cents=amount,  # Already an integer from Paystack
            raw=raw_flat,
            received_at=datetime.now(UTC),
        )

    async def verify_transaction(self, reference: str) -> PaymentStatus:
        """
        Server-side verification of a transaction.

        This is the second step of the two-step webhook verification pattern.
        After verifying the webhook signature locally, call this method to
        confirm the transaction status directly with Paystack's API.

        This is separate from verify_webhook() to allow the merchant-api to
        decide when to perform server-side verification (e.g., only for
        high-value transactions, or always as a security measure).

        Args:
            reference: Transaction reference to verify

        Returns:
            Current PaymentStatus from Paystack's API

        Raises:
            PaymentNotFoundError: Transaction doesn't exist
            AuthenticationError: Invalid API key
            NetworkError: Provider communication failure

        Example:
            # After webhook verification
            event = adapter.verify_webhook(headers, body)
            # Confirm with server-side verification
            status = await adapter.verify_transaction(event.reference)
            if status == PaymentStatus.SUCCEEDED:
                # Double-confirmed - safe to fulfill order
        """
        return await self.get_status(reference)

    async def refund(
        self, provider_payment_id: str, amount_cents: int | None = None
    ) -> PaymentResult:
        """
        Refund a payment (full or partial).

        CRITICAL: Amount is sent as an INTEGER (not string) for refund endpoint.
        This is different from the initialize endpoint which uses strings.

        Args:
            provider_payment_id: Paystack reference (used as payment ID)
            amount_cents: Amount to refund in cents. If None, full refund.

        Returns:
            PaymentResult with status=REFUNDED

        Raises:
            PaymentNotFoundError: Transaction doesn't exist
            RefundError: Transaction not refundable or amount exceeds original
            InvalidRequestError: Invalid refund parameters
            AuthenticationError: Invalid API key
            NetworkError: Provider communication failure

        Example:
            # Full refund
            result = await adapter.refund("ORDER-ABC123")

            # Partial refund (R50.00 of R100.00)
            result = await adapter.refund("ORDER-ABC123", amount_cents=5000)
        """
        try:
            # Build request payload
            # CRITICAL: amount is an INTEGER for refund endpoint (not string)
            payload: dict[str, Any] = {
                "transaction": provider_payment_id,
            }

            if amount_cents is not None:
                if amount_cents < 0:
                    raise InvalidRequestError(
                        f"Refund amount cannot be negative: {amount_cents}",
                        provider="paystack",
                    )
                payload["amount"] = amount_cents  # INTEGER format

            self.logger.info(
                "paystack_refund_request",
                provider_payment_id=provider_payment_id,
                amount_cents=amount_cents,
            )

            response = await self.client.post(
                "/refund",
                headers=self._get_headers(),
                json=payload,
            )

            # Handle error responses
            if response.status_code == 404:
                raise PaymentNotFoundError(
                    f"Transaction not found: {provider_payment_id}",
                    provider="paystack",
                )
            elif response.status_code == 401:
                raise AuthenticationError(
                    "Invalid Paystack API key", provider="paystack"
                )
            elif 400 <= response.status_code < 500:
                error_data = response.json()
                error_message = error_data.get("message", "Unknown error")
                raise RefundError(
                    f"Paystack refund error: {error_message}", provider="paystack"
                )
            elif response.status_code >= 500:
                raise NetworkError(
                    f"Paystack server error: {response.status_code}",
                    provider="paystack",
                )

            response.raise_for_status()
            data = response.json()

            if not data.get("status"):
                raise RefundError(
                    f"Paystack refund error: {data.get('message', 'Unknown error')}",
                    provider="paystack",
                )

            # Extract refund data
            response_data = data["data"]
            transaction_data = response_data.get("transaction", {})
            refund_data = response_data.get("refund", {})

            # CRITICAL: Use reference field, not id
            reference = transaction_data.get("reference", provider_payment_id)

            self.logger.info(
                "paystack_refund_processed",
                reference=reference,
                refund_id=refund_data.get("id"),
                amount_cents=refund_data.get("amount"),
            )

            # Flatten nested response for raw field (must be scalar values only)
            raw_flat = {
                "reference": reference,
                "refund_id": str(refund_data.get("id", "")),
                "amount": refund_data.get("amount", 0),
                "status": refund_data.get("status", ""),
            }

            return PaymentResult(
                provider="paystack",
                provider_payment_id=reference,  # Use reference, not id
                reference=reference,
                status=PaymentStatus.REFUNDED,
                redirect_url=None,
                raw=raw_flat,
            )

        except httpx.HTTPError as e:
            self.logger.error("paystack_http_error", error=str(e))
            raise NetworkError(
                f"Failed to communicate with Paystack: {e}", provider="paystack"
            ) from e


# Made with Bob