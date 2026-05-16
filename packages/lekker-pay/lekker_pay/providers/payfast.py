"""
PayFast payment adapter for Lekker Pay.

This is the reference adapter implementation. All other provider adapters
should follow the patterns established here.

CRITICAL SECURITY NOTES:
- Checkout signature uses DOCUMENTATION ORDER, not alphabetical
- Empty passphrase must be OMITTED, not appended as empty string
- All signature comparisons use hmac.compare_digest (constant-time)
- Money is always int cents internally, formatted to provider format at wire boundary
- ITN signature is in POST body, not headers
- Refunds API uses DIFFERENT signature scheme (alphabetical, header-based)
"""

import hashlib
import hmac
import urllib.parse
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import ClassVar

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

# PayFast checkout signature field order (DOCUMENTATION ORDER, NOT ALPHABETICAL)
# This is the #1 integration bug. Do not sort alphabetically.
# Source: PayFast "Create your checkout form" docs, Step 2, signature section
_CHECKOUT_SIGNATURE_FIELD_ORDER = (
    # Merchant Details
    "merchant_id",
    "merchant_key",
    "return_url",
    "cancel_url",
    "notify_url",
    # Buyer Details
    "name_first",
    "name_last",
    "email_address",
    "cell_number",
    # Transaction Details
    "m_payment_id",
    "amount",
    "item_name",
    "item_description",
    "custom_int1",
    "custom_int2",
    "custom_int3",
    "custom_int4",
    "custom_int5",
    "custom_str1",
    "custom_str2",
    "custom_str3",
    "custom_str4",
    "custom_str5",
    # Transaction Options
    "email_confirmation",
    "confirmation_address",
    # Payment Method
    "payment_method",
    # Recurring Billing
    "subscription_type",
    "billing_date",
    "recurring_amount",
    "frequency",
    "cycles",
)

# API endpoints
_SANDBOX_PROCESS_URL = "https://sandbox.payfast.co.za/eng/process"
_LIVE_PROCESS_URL = "https://www.payfast.co.za/eng/process"
_SANDBOX_VALIDATE_URL = "https://sandbox.payfast.co.za/eng/query/validate"
_LIVE_VALIDATE_URL = "https://www.payfast.co.za/eng/query/validate"
_REFUNDS_API_BASE = "https://api.payfast.co.za/refunds"
_REFUNDS_API_VERSION = "v1"


@dataclass(frozen=True, slots=True)
class PayFastConfig:
    """
    PayFast-specific configuration.

    All fields are required except passphrase (which may be empty if disabled
    in PayFast dashboard). Configuration is injected via constructor - no
    environment variable reads inside the adapter.

    Example:
        config = PayFastConfig(
            merchant_id="10000100",
            merchant_key="46f0cd694581a",
            passphrase="jt7NOE43FZPn",
            sandbox=True,
            timeout=30.0
        )
    """

    merchant_id: str
    merchant_key: str
    passphrase: str  # May be empty string if disabled in PayFast dashboard
    sandbox: bool = True
    timeout: float = 30.0


class PayFastAdapter(BasePaymentAdapter):
    """
    PayFast payment adapter.

    PayFast uses a redirect-based payment flow with MD5 signature verification.
    The checkout signature uses documentation order (not alphabetical), and the
    ITN signature is embedded in the POST body (not headers).

    The Refunds API is a completely separate surface with different conventions:
    - Header-based authentication
    - Alphabetically-sorted signature fields
    - JSON body (not form-encoded)
    - Amount in cents (not rand strings)

    Example:
        config = PayFastConfig(
            merchant_id="10000100",
            merchant_key="46f0cd694581a",
            passphrase="jt7NOE43FZPn",
            sandbox=True
        )
        adapter = PayFastAdapter(config)

        # Create payment (returns redirect URL)
        result = await adapter.create_payment(intent)
        # Redirect customer to result.redirect_url

        # Verify ITN webhook (two-step pattern)
        event = adapter.verify_webhook(request.headers, await request.body())
        if await adapter.validate_itn(await request.body()):
            # Mark order as paid
            pass
    """

    provider_name: ClassVar[str] = "payfast"

    def __init__(self, config: PayFastConfig | ProviderConfig) -> None:
        """
        Initialize PayFast adapter with configuration.

        Args:
            config: PayFast-specific configuration or generic ProviderConfig
        """
        # Convert ProviderConfig to PayFastConfig if needed
        if isinstance(config, ProviderConfig):
            self.config = PayFastConfig(
                merchant_id=config.merchant_id or "",
                merchant_key=config.merchant_key or "",
                passphrase=config.passphrase or "",
                sandbox=config.sandbox,
                timeout=30.0,  # Default timeout
            )
        else:
            self.config = config
            
        self.logger = logger.bind(provider="payfast", sandbox=self.config.sandbox)

        # HTTP client for async operations (validate_itn, refund)
        self.client = httpx.AsyncClient(
            timeout=self.config.timeout,
            headers={"User-Agent": "LekkerPay/0.1.0"},
        )

    def _get_process_url(self) -> str:
        """Get the PayFast process URL (sandbox or live)."""
        return _SANDBOX_PROCESS_URL if self.config.sandbox else _LIVE_PROCESS_URL

    def _get_validate_url(self) -> str:
        """Get the PayFast ITN validation URL (sandbox or live)."""
        return _SANDBOX_VALIDATE_URL if self.config.sandbox else _LIVE_VALIDATE_URL

    def _cents_to_rands_string(self, cents: int) -> str:
        """
        Convert integer cents to PayFast's rand string format.

        PayFast checkout expects amounts as 2-decimal rand strings (e.g., "150.00").
        Never use float for this conversion - use Decimal to avoid drift.

        Note: The Refunds API uses cents directly, not this format.

        Args:
            cents: Amount in cents (e.g., 15000 for R150.00)

        Returns:
            Formatted rand string (e.g., "150.00")

        Raises:
            InvalidRequestError: If cents is negative

        Example:
            >>> _cents_to_rands_string(10000)
            "100.00"
            >>> _cents_to_rands_string(8550)
            "85.50"
        """
        if cents < 0:
            raise InvalidRequestError(
                f"Amount cannot be negative: {cents} cents", provider="payfast"
            )

        rands = Decimal(cents) / Decimal(100)
        return f"{rands:.2f}"

    def _build_checkout_signature(self, params: dict[str, str]) -> str:
        """
        Build MD5 signature for PayFast checkout.

        CRITICAL: Uses DOCUMENTATION ORDER, not alphabetical order.
        This is the #1 PayFast integration bug.

        CRITICAL: Empty passphrase must be OMITTED, not appended as empty string.
        This caused 100% production failure in Nov 2025.

        Args:
            params: Payment parameters (must not include 'signature' key)

        Returns:
            MD5 signature hex string
        """
        # Build parameter string in documentation order
        param_pairs = []
        for field in _CHECKOUT_SIGNATURE_FIELD_ORDER:
            if field in params and params[field]:
                # URL encode using quote_plus (spaces become +, not %20)
                # Do NOT post-process with .replace("+", " ") - that's a bug in
                # PayFast's own published Python example
                value = urllib.parse.quote_plus(str(params[field]).strip())
                param_pairs.append(f"{field}={value}")

        payload = "&".join(param_pairs)

        # Append passphrase if present (truthy check, not is None)
        # Empty passphrase must be omitted entirely
        if self.config.passphrase:
            payload += "&passphrase=" + urllib.parse.quote_plus(self.config.passphrase.strip())

        # MD5 hash
        return hashlib.md5(payload.encode()).hexdigest()

    def _build_refunds_signature(self, timestamp: str, payload: str) -> str:
        """
        Build MD5 signature for PayFast Refunds API.

        The Refunds API uses a DIFFERENT signature scheme than checkout:
        - Parameters sorted ALPHABETICALLY (not documentation order)
        - Includes headers in signature (merchant-id, version, timestamp)
        - JSON body (not form-encoded)

        Args:
            timestamp: ISO 8601 timestamp for request
            payload: JSON request body

        Returns:
            MD5 signature hex string
        """
        # Build signature string: headers + body, alphabetically sorted
        parts = [
            f"merchant-id={self.config.merchant_id}",
            f"passphrase={self.config.passphrase}" if self.config.passphrase else "",
            f"timestamp={timestamp}",
            f"version={_REFUNDS_API_VERSION}",
        ]

        # Remove empty parts and sort alphabetically
        parts = [p for p in parts if p]
        parts.sort()

        signature_string = "&".join(parts)
        if payload:
            signature_string += payload

        return hashlib.md5(signature_string.encode()).hexdigest()

    def _parse_itn_amount(self, amount_gross: str) -> int:
        """
        Parse PayFast ITN amount_gross to integer cents.

        PayFast sends amounts as decimal rand strings (e.g., "100.00").
        Parse via Decimal, never float.

        Args:
            amount_gross: Rand string from ITN (e.g., "100.00")

        Returns:
            Amount in cents (e.g., 10000)

        Raises:
            InvalidRequestError: If amount cannot be parsed
        """
        try:
            rands = Decimal(amount_gross)
            cents = int(rands * 100)
            return cents
        except (ValueError, ArithmeticError) as e:
            raise InvalidRequestError(
                f"Invalid amount_gross format: {amount_gross}", provider="payfast"
            ) from e

    def _map_status(self, payfast_status: str) -> PaymentStatus:
        """
        Map PayFast payment status to unified PaymentStatus.

        Args:
            payfast_status: PayFast status (COMPLETE, FAILED, CANCELLED)

        Returns:
            Unified PaymentStatus

        Raises:
            InvalidRequestError: If status is unknown
        """
        status_map = {
            "COMPLETE": PaymentStatus.SUCCEEDED,
            "FAILED": PaymentStatus.FAILED,
            "CANCELLED": PaymentStatus.CANCELLED,
        }

        if payfast_status not in status_map:
            raise InvalidRequestError(
                f"Unknown PayFast status: {payfast_status}", provider="payfast"
            )

        return status_map[payfast_status]

    def _map_event_type(self, payfast_status: str) -> str:
        """
        Map PayFast status to webhook event type.

        Args:
            payfast_status: PayFast status (COMPLETE, FAILED, CANCELLED)

        Returns:
            Event type string ("payment.succeeded", "payment.failed", "payment.refunded")
        """
        if payfast_status == "COMPLETE":
            return "payment.succeeded"
        else:
            # FAILED and CANCELLED both map to payment.failed
            return "payment.failed"

    async def create_payment(self, intent: PaymentIntent) -> PaymentResult:
        """
        Create a PayFast payment (redirect flow).

        PayFast is a redirect-based flow - this method builds a signed parameter
        set and returns a redirect URL. The customer is redirected to PayFast's
        payment page, and the result arrives via ITN webhook.

        Note: provider_payment_id is set to intent.reference as a placeholder.
        The real pf_payment_id is assigned by PayFast and arrives via ITN.

        Args:
            intent: Provider-agnostic payment request

        Returns:
            PaymentResult with status=PENDING and redirect_url

        Example:
            result = await adapter.create_payment(intent)
            # Redirect customer to result.redirect_url
        """
        # Split customer name into first/last (PayFast requires separate fields)
        name_parts = intent.customer_name.strip().split(maxsplit=1)
        name_first = name_parts[0]
        name_last = name_parts[1] if len(name_parts) > 1 else ""

        # Build payment parameters
        params = {
            "merchant_id": self.config.merchant_id,
            "merchant_key": self.config.merchant_key,
            "return_url": str(intent.return_url),
            "cancel_url": str(intent.cancel_url),
            "notify_url": str(intent.webhook_url),
            "name_first": name_first,
            "name_last": name_last,
            "email_address": intent.customer_email,
            "m_payment_id": intent.reference,
            "amount": self._cents_to_rands_string(intent.amount_cents),
            "item_name": f"Payment {intent.reference}",
            "item_description": f"Payment for order {intent.reference}",
        }

        # Add metadata as custom fields (max 5 string fields)
        for i, (key, value) in enumerate(list(intent.metadata.items())[:5], start=1):
            params[f"custom_str{i}"] = f"{key}:{value}"

        # Generate signature
        signature = self._build_checkout_signature(params)
        params["signature"] = signature

        # Build redirect URL
        query_string = urllib.parse.urlencode(params)
        redirect_url = f"{self._get_process_url()}?{query_string}"

        self.logger.info(
            "payment_created",
            reference=intent.reference,
            amount_cents=intent.amount_cents,
        )

        return PaymentResult(
            provider="payfast",
            provider_payment_id=intent.reference,  # Placeholder until ITN arrives
            reference=intent.reference,
            status=PaymentStatus.PENDING,
            redirect_url=redirect_url,  # type: ignore
            raw=dict(params),  # Cast to satisfy type checker
        )

    async def get_status(self, provider_payment_id: str) -> PaymentStatus:
        """
        Query payment status (limited functionality for PayFast).

        PayFast's redirect flow does not provide a status query API.
        This method returns PENDING and logs a warning. Merchants should
        rely on ITN webhooks for payment status updates.

        Args:
            provider_payment_id: Provider's payment ID (or merchant reference)

        Returns:
            PaymentStatus.PENDING (always)
        """
        self.logger.warning(
            "get_status_not_supported",
            provider_payment_id=provider_payment_id,
            message="PayFast redirect flow has no status query API. Rely on ITN webhooks.",
        )
        return PaymentStatus.PENDING

    def verify_webhook(self, headers: Mapping[str, str], body: bytes) -> WebhookEvent:
        """
        Verify PayFast ITN webhook signature and parse event.

        CRITICAL SECURITY:
        - Signature is in POST body (not headers) as 'signature' field
        - Uses constant-time comparison (hmac.compare_digest)
        - Uses raw body to avoid double-encoding issues
        - Preserves field order from PayFast (no re-sorting)

        This method is SYNCHRONOUS (no async/await). After calling this,
        the merchant-api should call validate_itn() for server-to-server
        confirmation:

            event = adapter.verify_webhook(headers, body)  # sync
            if await adapter.validate_itn(body):           # async
                # Mark order as paid

        Args:
            headers: HTTP headers (unused for PayFast, but required by contract)
            body: Raw POST body as bytes

        Returns:
            Parsed and verified WebhookEvent

        Raises:
            SignatureMismatchError: Signature verification failed
            InvalidRequestError: Malformed webhook payload
        """
        del headers  # Unused for PayFast (signature is in body)

        # Decode body to string
        try:
            body_str = body.decode("utf-8")
        except UnicodeDecodeError as e:
            raise InvalidRequestError("Malformed ITN body encoding", provider="payfast") from e

        # Split on & to get individual key=value pairs in their ORIGINAL encoded form
        # This avoids the decode/re-encode round-trip that causes @ and other chars to mismatch
        pairs = body_str.split("&")
        
        received_signature = None
        sig_parts = []
        parsed_fields: dict[str, str] = {}
        
        for pair in pairs:
            if "=" not in pair:
                continue
            key, value = pair.split("=", 1)
            
            if key == "signature":
                received_signature = value
            else:
                # Use ORIGINAL encoded form for signature verification
                sig_parts.append(pair)
                # Decode value separately for the event payload
                parsed_fields[key] = urllib.parse.unquote_plus(value)
        
        # Validate required fields
        required_fields = ["m_payment_id", "pf_payment_id", "payment_status", "amount_gross"]
        for field in required_fields:
            if field not in parsed_fields:
                raise InvalidRequestError(
                    f"Missing required ITN field: {field}", provider="payfast"
                )
        
        if not received_signature:
            raise SignatureMismatchError("Missing signature in ITN", provider="payfast")
        
        # Build signature payload from original encoded pairs
        payload = "&".join(sig_parts)
        
        # Append passphrase if present
        if self.config.passphrase:
            payload += "&passphrase=" + urllib.parse.quote_plus(self.config.passphrase.strip())
        
        expected_signature = hashlib.md5(payload.encode("utf-8")).hexdigest()
        
        # TEMPORARY DEBUG LOGGING - Remove after testing
        self.logger.debug(
            "payfast.itn_signature_check",
            received=received_signature,
            expected=expected_signature,
            payload_string=payload,
        )
        
        # Constant-time comparison (prevent timing attacks)
        if not hmac.compare_digest(received_signature, expected_signature):
            self.logger.warning(
                "signature_mismatch",
                received=received_signature,
                expected=expected_signature,
            )
            raise SignatureMismatchError("ITN signature verification failed", provider="payfast")
        
        # Parse and map status
        payfast_status = parsed_fields["payment_status"]
        status = self._map_status(payfast_status)
        event_type = self._map_event_type(payfast_status)
        
        # Parse amount
        amount_cents = self._parse_itn_amount(parsed_fields["amount_gross"])
        
        self.logger.info(
            "webhook_verified",
            reference=parsed_fields["m_payment_id"],
            pf_payment_id=parsed_fields["pf_payment_id"],
            status=status.value,
        )
        
        return WebhookEvent(
            provider="payfast",
            event_type=event_type,  # type: ignore
            provider_payment_id=parsed_fields["pf_payment_id"],
            reference=parsed_fields["m_payment_id"],
            amount_cents=amount_cents,
            raw=dict(parsed_fields),  # Cast to satisfy type checker
            received_at=datetime.now(UTC),
        )

    async def validate_itn(self, body: bytes) -> bool:
        """
        Perform server-to-server ITN validation with PayFast.

        After verifying the ITN signature with verify_webhook(), call this
        method to confirm the ITN originated from PayFast. This is layer 4
        of PayFast's security model.

        Args:
            body: Raw ITN POST body (same bytes passed to verify_webhook)

        Returns:
            True if PayFast confirms the ITN is valid

        Raises:
            NetworkError: Communication with PayFast failed

        Example:
            event = adapter.verify_webhook(headers, body)
            if await adapter.validate_itn(body):
                # Mark order as paid
        """
        try:
            response = await self.client.post(
                self._get_validate_url(),
                content=body,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()

            is_valid = response.text.strip() == "VALID"

            self.logger.info(
                "itn_validated",
                is_valid=is_valid,
                response_text=response.text.strip(),
            )

            return is_valid

        except httpx.HTTPError as e:
            self.logger.error("itn_validation_failed", error=str(e))
            raise NetworkError(f"ITN validation request failed: {e}", provider="payfast") from e

    async def refund(
        self, provider_payment_id: str, amount_cents: int | None = None
    ) -> PaymentResult:
        """
        Refund a PayFast payment (full or partial).

        The Refunds API uses a DIFFERENT signature scheme than checkout:
        - Header-based authentication (not form fields)
        - Alphabetically-sorted parameters (not documentation order)
        - JSON body (not form-encoded)
        - Amount in CENTS (not rand strings)

        Args:
            provider_payment_id: PayFast's pf_payment_id from ITN
            amount_cents: Amount to refund in cents. If None, full refund.

        Returns:
            PaymentResult with status=REFUNDED

        Raises:
            PaymentNotFoundError: Payment doesn't exist (404)
            RefundError: Refund failed (payment not refundable, amount exceeds original)
            AuthenticationError: Invalid credentials (401)
            NetworkError: Communication failure

        Example:
            # Full refund
            result = await adapter.refund("1234567")

            # Partial refund (R50.00)
            result = await adapter.refund("1234567", amount_cents=5000)
        """
        # Build request
        timestamp = datetime.now(UTC).isoformat()
        payload = f'{{"amount":{amount_cents}}}' if amount_cents else ""

        signature = self._build_refunds_signature(timestamp, payload)

        headers = {
            "merchant-id": self.config.merchant_id,
            "version": _REFUNDS_API_VERSION,
            "timestamp": timestamp,
            "signature": signature,
        }

        # Build URL with testing flag for sandbox
        url = f"{_REFUNDS_API_BASE}/{provider_payment_id}"
        if self.config.sandbox:
            url += "?testing=true"

        try:
            response = await self.client.post(
                url,
                headers=headers,
                content=payload if payload else None,
                timeout=self.config.timeout,
            )

            if response.status_code == 404:
                raise PaymentNotFoundError(
                    f"Payment not found: {provider_payment_id}", provider="payfast"
                )
            elif response.status_code == 401:
                raise AuthenticationError("Invalid refund credentials", provider="payfast")
            elif response.status_code >= 400:
                error_detail = response.text[:200]
                raise RefundError(f"Refund failed: {error_detail}", provider="payfast")

            response.raise_for_status()

            self.logger.info(
                "refund_completed",
                provider_payment_id=provider_payment_id,
                amount_cents=amount_cents,
            )

            return PaymentResult(
                provider="payfast",
                provider_payment_id=provider_payment_id,
                reference=provider_payment_id,  # No merchant reference available
                status=PaymentStatus.REFUNDED,
                redirect_url=None,
                raw={"refund_amount_cents": amount_cents, "response": response.text},
            )

        except httpx.HTTPError as e:
            self.logger.error(
                "refund_network_error",
                provider_payment_id=provider_payment_id,
                error=str(e),
            )
            raise NetworkError(f"Refund request failed: {e}", provider="payfast") from e

    async def __aenter__(self) -> "PayFastAdapter":
        """Async context manager entry."""
        return self

    async def __aexit__(self, *args: object) -> None:
        """Async context manager exit - close HTTP client."""
        await self.client.aclose()


# Made with Bob
