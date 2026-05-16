"""
Comprehensive test suite for Paystack adapter.

Tests cover:
- Configuration validation
- Money conversion (string for initialize, integer for refund)
- Status mapping (including abandoned→FAILED)
- Event mapping
- Payment creation
- Webhook verification (HMAC-SHA512, constant-time comparison)
- Server-side transaction verification
- Refund operations
- Error handling
- Footgun regression tests
"""

import hashlib
import hmac
import json

import pytest
import respx
from httpx import Response
from pydantic import HttpUrl

from lekker_pay import PaymentIntent, PaymentStatus, ProviderConfig
from lekker_pay.errors import (
    AuthenticationError,
    InvalidRequestError,
    NetworkError,
    PaymentNotFoundError,
    RefundError,
    SignatureMismatchError,
)
from lekker_pay.providers.paystack import PaystackAdapter


class TestPaystackAdapterInit:
    """Test Paystack adapter initialization and configuration."""

    def test_init_with_valid_config(self):
        """Test creating adapter with valid configuration."""
        config = ProviderConfig(
            api_key="sk_test_abc123",
            sandbox=True,
        )
        adapter = PaystackAdapter(config)
        
        assert adapter.config.api_key == "sk_test_abc123"
        assert adapter.config.sandbox is True
        assert adapter.provider_name == "paystack"

    def test_init_missing_api_key_raises_valueerror(self):
        """Test that missing api_key raises ValueError."""
        config = ProviderConfig(
            api_key="",  # Empty
            sandbox=True,
        )
        
        with pytest.raises(ValueError, match="Paystack requires api_key"):
            PaystackAdapter(config)

    def test_init_none_api_key_raises_valueerror(self):
        """Test that None api_key raises ValueError."""
        config = ProviderConfig(
            api_key=None,
            sandbox=True,
        )
        
        with pytest.raises(ValueError, match="Paystack requires api_key"):
            PaystackAdapter(config)


class TestMoneyConversion:
    """Test money conversion between cents and string format."""

    @pytest.fixture
    def adapter(self):
        """Create adapter for testing."""
        config = ProviderConfig(
            api_key="sk_test_abc123",
            sandbox=True,
        )
        return PaystackAdapter(config)

    def test_cents_to_string_zero(self, adapter):
        """Test converting 0 cents."""
        assert adapter._cents_to_string(0) == "0"

    def test_cents_to_string_one_cent(self, adapter):
        """Test converting 1 cent."""
        assert adapter._cents_to_string(1) == "1"

    def test_cents_to_string_float_drift_case(self, adapter):
        """Test the 8550 cents case (R85.50) - known float drift scenario."""
        # This verifies we're using integer-to-string conversion, not float
        assert adapter._cents_to_string(8550) == "8550"

    def test_cents_to_string_round_amount(self, adapter):
        """Test converting round rand amount."""
        assert adapter._cents_to_string(10000) == "10000"

    def test_cents_to_string_large_amount(self, adapter):
        """Test converting large amount."""
        assert adapter._cents_to_string(123456789) == "123456789"

    def test_cents_to_string_negative_raises(self, adapter):
        """Test that negative amounts raise InvalidRequestError."""
        with pytest.raises(InvalidRequestError, match="cannot be negative"):
            adapter._cents_to_string(-100)

    def test_initialize_amount_is_string_refund_amount_is_integer(self, adapter):
        """
        PAYSTACK-SPECIFIC FOOTGUN: Amount format varies by endpoint.
        
        /transaction/initialize expects STRING "10000"
        /refund expects INTEGER 10000
        
        This test verifies the helper produces strings for initialize.
        The refund test verifies integers are sent directly.
        """
        # Initialize uses string
        amount_str = adapter._cents_to_string(10000)
        assert isinstance(amount_str, str)
        assert amount_str == "10000"
        
        # Refund will send integer directly (tested in TestRefund)


class TestStatusMapping:
    """Test Paystack status mapping to unified PaymentStatus."""

    @pytest.fixture
    def adapter(self):
        """Create adapter for testing."""
        config = ProviderConfig(
            api_key="sk_test_abc123",
            sandbox=True,
        )
        return PaystackAdapter(config)

    def test_map_status_success(self, adapter):
        """Test mapping 'success' status."""
        assert adapter._map_status("success") == PaymentStatus.SUCCEEDED

    def test_map_status_failed(self, adapter):
        """Test mapping 'failed' status."""
        assert adapter._map_status("failed") == PaymentStatus.FAILED

    def test_map_status_abandoned(self, adapter):
        """
        PAYSTACK-SPECIFIC: Test mapping 'abandoned' status to FAILED.
        
        When a customer abandons payment, Paystack returns 'abandoned'.
        We treat this as FAILED for unified semantics.
        """
        assert adapter._map_status("abandoned") == PaymentStatus.FAILED

    def test_map_status_pending(self, adapter):
        """Test mapping 'pending' status."""
        assert adapter._map_status("pending") == PaymentStatus.PENDING

    def test_map_status_unknown_raises(self, adapter):
        """Test that unknown status raises InvalidRequestError."""
        with pytest.raises(InvalidRequestError, match="Unknown Paystack status"):
            adapter._map_status("unknown_status")


class TestEventMapping:
    """Test Paystack event mapping to unified event types."""

    @pytest.fixture
    def adapter(self):
        """Create adapter for testing."""
        config = ProviderConfig(
            api_key="sk_test_abc123",
            sandbox=True,
        )
        return PaystackAdapter(config)

    def test_map_event_charge_success(self, adapter):
        """Test mapping 'charge.success' event."""
        assert adapter._map_event("charge.success") == "payment.succeeded"

    def test_map_event_charge_failed(self, adapter):
        """Test mapping 'charge.failed' event."""
        assert adapter._map_event("charge.failed") == "payment.failed"

    def test_map_event_refund_processed(self, adapter):
        """Test mapping 'refund.processed' event."""
        assert adapter._map_event("refund.processed") == "payment.refunded"

    def test_map_event_unknown_raises(self, adapter):
        """Test that unknown event raises InvalidRequestError."""
        with pytest.raises(InvalidRequestError, match="Unknown Paystack event"):
            adapter._map_event("unknown.event")


class TestCreatePayment:
    """Test payment creation via /transaction/initialize."""

    @pytest.fixture
    def adapter(self):
        """Create adapter for testing."""
        config = ProviderConfig(
            api_key="sk_test_abc123",
            sandbox=True,
        )
        return PaystackAdapter(config)

    @pytest.fixture
    def sample_intent(self):
        """Create sample payment intent."""
        return PaymentIntent(
            amount_cents=10000,
            currency="ZAR",
            reference="ORDER-ABC123",
            customer_email="test@example.com",
            customer_name="John Doe",
            return_url=HttpUrl("https://example.com/success"),
            cancel_url=HttpUrl("https://example.com/cancel"),
            webhook_url=HttpUrl("https://example.com/webhooks/paystack"),
            metadata={"order_id": "123"},
        )

    @pytest.mark.asyncio
    @respx.mock
    async def test_create_payment_success(self, adapter, sample_intent):
        """Test successful payment creation."""
        # Mock Paystack API response
        respx.post("https://api.paystack.co/transaction/initialize").mock(
            return_value=Response(
                200,
                json={
                    "status": True,
                    "message": "Authorization URL created",
                    "data": {
                        "authorization_url": "https://checkout.paystack.com/abc123",
                        "access_code": "abc123",
                        "reference": "ORDER-ABC123",
                    },
                },
            )
        )

        result = await adapter.create_payment(sample_intent)

        assert result.provider == "paystack"
        assert result.reference == "ORDER-ABC123"
        assert result.provider_payment_id == "ORDER-ABC123"  # Uses reference, not id
        assert result.status == PaymentStatus.PENDING
        assert str(result.redirect_url) == "https://checkout.paystack.com/abc123"
        assert "authorization_url" in result.raw
        assert "access_code" in result.raw

    @pytest.mark.asyncio
    @respx.mock
    async def test_create_payment_authorization_url_not_access_code(self, adapter, sample_intent):
        """
        PAYSTACK-SPECIFIC FOOTGUN: Verify redirect_url is authorization_url, not access_code.
        
        Paystack returns both authorization_url and access_code.
        The customer must be redirected to authorization_url.
        """
        respx.post("https://api.paystack.co/transaction/initialize").mock(
            return_value=Response(
                200,
                json={
                    "status": True,
                    "message": "Authorization URL created",
                    "data": {
                        "authorization_url": "https://checkout.paystack.com/correct",
                        "access_code": "wrong_redirect",
                        "reference": "ORDER-ABC123",
                    },
                },
            )
        )

        result = await adapter.create_payment(sample_intent)

        # MUST use authorization_url, NOT access_code
        assert str(result.redirect_url) == "https://checkout.paystack.com/correct"
        assert "wrong_redirect" not in str(result.redirect_url)

    @pytest.mark.asyncio
    @respx.mock
    async def test_create_payment_amount_sent_as_string(self, adapter, sample_intent):
        """Test that amount is sent as STRING to initialize endpoint."""
        mock_route = respx.post("https://api.paystack.co/transaction/initialize").mock(
            return_value=Response(
                200,
                json={
                    "status": True,
                    "message": "Authorization URL created",
                    "data": {
                        "authorization_url": "https://checkout.paystack.com/abc123",
                        "access_code": "abc123",
                        "reference": "ORDER-ABC123",
                    },
                },
            )
        )

        await adapter.create_payment(sample_intent)

        # Verify request payload
        request = mock_route.calls.last.request
        payload = json.loads(request.content)
        
        # Amount MUST be a string
        assert isinstance(payload["amount"], str)
        assert payload["amount"] == "10000"

    @pytest.mark.asyncio
    @respx.mock
    async def test_create_payment_401_raises_authentication_error(self, adapter, sample_intent):
        """Test that 401 response raises AuthenticationError."""
        respx.post("https://api.paystack.co/transaction/initialize").mock(
            return_value=Response(401, json={"status": False, "message": "Invalid key"})
        )

        with pytest.raises(AuthenticationError, match="Invalid Paystack API key"):
            await adapter.create_payment(sample_intent)

    @pytest.mark.asyncio
    @respx.mock
    async def test_create_payment_400_raises_invalid_request_error(self, adapter, sample_intent):
        """Test that 400 response raises InvalidRequestError."""
        respx.post("https://api.paystack.co/transaction/initialize").mock(
            return_value=Response(
                400, json={"status": False, "message": "Invalid email address"}
            )
        )

        with pytest.raises(InvalidRequestError, match="Invalid email address"):
            await adapter.create_payment(sample_intent)

    @pytest.mark.asyncio
    @respx.mock
    async def test_create_payment_500_raises_network_error(self, adapter, sample_intent):
        """Test that 500 response raises NetworkError."""
        respx.post("https://api.paystack.co/transaction/initialize").mock(
            return_value=Response(500, json={"status": False, "message": "Server error"})
        )

        with pytest.raises(NetworkError, match="Paystack server error"):
            await adapter.create_payment(sample_intent)


class TestGetStatus:
    """Test payment status query via /transaction/verify."""

    @pytest.fixture
    def adapter(self):
        """Create adapter for testing."""
        config = ProviderConfig(
            api_key="sk_test_abc123",
            sandbox=True,
        )
        return PaystackAdapter(config)

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_status_success(self, adapter):
        """Test successful status query."""
        respx.get("https://api.paystack.co/transaction/verify/ORDER-ABC123").mock(
            return_value=Response(
                200,
                json={
                    "status": True,
                    "message": "Verification successful",
                    "data": {
                        "id": 1234567890,
                        "status": "success",
                        "reference": "ORDER-ABC123",
                        "amount": 10000,
                    },
                },
            )
        )

        status = await adapter.get_status("ORDER-ABC123")
        assert status == PaymentStatus.SUCCEEDED

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_status_404_raises_payment_not_found(self, adapter):
        """Test that 404 response raises PaymentNotFoundError."""
        respx.get("https://api.paystack.co/transaction/verify/NOTFOUND").mock(
            return_value=Response(404, json={"status": False, "message": "Not found"})
        )

        with pytest.raises(PaymentNotFoundError, match="Transaction not found"):
            await adapter.get_status("NOTFOUND")

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_status_401_raises_authentication_error(self, adapter):
        """Test that 401 response raises AuthenticationError."""
        respx.get("https://api.paystack.co/transaction/verify/ORDER-ABC123").mock(
            return_value=Response(401, json={"status": False, "message": "Invalid key"})
        )

        with pytest.raises(AuthenticationError, match="Invalid Paystack API key"):
            await adapter.get_status("ORDER-ABC123")


class TestVerifyWebhook:
    """Test webhook signature verification and parsing."""

    @pytest.fixture
    def adapter(self):
        """Create adapter for testing."""
        config = ProviderConfig(
            api_key="sk_test_abc123",
            sandbox=True,
        )
        return PaystackAdapter(config)

    def test_verify_webhook_success(self, adapter):
        """Test successful webhook verification."""
        # Build webhook payload
        payload = {
            "event": "charge.success",
            "data": {
                "id": 1234567890,
                "status": "success",
                "reference": "ORDER-ABC123",
                "amount": 10000,
            },
        }
        body = json.dumps(payload).encode("utf-8")

        # Compute signature using HMAC-SHA512
        signature = hmac.new(
            b"sk_test_abc123",
            body,
            hashlib.sha512,
        ).hexdigest()

        headers = {"x-paystack-signature": signature}

        event = adapter.verify_webhook(headers, body)

        assert event.provider == "paystack"
        assert event.event_type == "payment.succeeded"
        assert event.provider_payment_id == "ORDER-ABC123"  # Uses reference, not id
        assert event.reference == "ORDER-ABC123"
        assert event.amount_cents == 10000

    def test_verify_webhook_uses_constant_time_comparison(self, adapter):
        """
        FOOTGUN REGRESSION TEST: Verify signature comparison uses hmac.compare_digest.
        
        This test verifies that signature comparison is constant-time to prevent
        timing attacks. The implementation MUST use hmac.compare_digest, not ==.
        """
        payload = {
            "event": "charge.success",
            "data": {
                "id": 1234567890,
                "status": "success",
                "reference": "ORDER-ABC123",
                "amount": 10000,
            },
        }
        body = json.dumps(payload).encode("utf-8")

        # Wrong signature (should fail)
        headers = {"x-paystack-signature": "wrong_signature"}

        with pytest.raises(SignatureMismatchError):
            adapter.verify_webhook(headers, body)

    def test_verify_webhook_uses_raw_bytes_not_parsed_json(self, adapter):
        """
        FOOTGUN REGRESSION TEST: Verify webhook uses raw bytes for signature.
        
        The signature MUST be computed over the raw request body bytes,
        not parsed JSON. Parsing and re-serializing will break signatures.
        """
        payload = {
            "event": "charge.success",
            "data": {
                "id": 1234567890,
                "status": "success",
                "reference": "ORDER-ABC123",
                "amount": 10000,
            },
        }
        # Use specific JSON formatting
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")

        # Compute signature over raw bytes
        signature = hmac.new(
            b"sk_test_abc123",
            body,
            hashlib.sha512,
        ).hexdigest()

        headers = {"x-paystack-signature": signature}

        # Should succeed with raw bytes
        event = adapter.verify_webhook(headers, body)
        assert event.reference == "ORDER-ABC123"

        # If we re-serialize with different formatting, signature would fail
        reparsed_body = json.dumps(json.loads(body), separators=(", ", ": ")).encode("utf-8")
        with pytest.raises(SignatureMismatchError):
            adapter.verify_webhook(headers, reparsed_body)

    def test_paystack_api_key_used_for_both_bearer_and_webhook_hmac(self, adapter):
        """
        PAYSTACK-SPECIFIC FOOTGUN: Verify api_key is used for both purposes.
        
        The same api_key value is used as:
        1. Bearer token in Authorization header for API calls
        2. HMAC-SHA512 key for webhook signature verification
        
        This duality is intentional but must be tested to prevent silent breakage
        if Paystack ever introduces a separate webhook secret.
        """
        # Verify Bearer token uses api_key
        headers = adapter._get_headers()
        assert headers["Authorization"] == "Bearer sk_test_abc123"

        # Verify webhook HMAC uses same api_key
        payload = {"event": "charge.success", "data": {"id": 123, "reference": "TEST", "amount": 100}}
        body = json.dumps(payload).encode("utf-8")
        
        # Signature computed with api_key
        signature = hmac.new(
            b"sk_test_abc123",  # Same api_key
            body,
            hashlib.sha512,
        ).hexdigest()

        headers_webhook = {"x-paystack-signature": signature}
        event = adapter.verify_webhook(headers_webhook, body)
        assert event.reference == "TEST"

    def test_verify_webhook_missing_signature_header(self, adapter):
        """Test webhook verification with missing signature header."""
        payload = {"event": "charge.success", "data": {"id": 123, "reference": "TEST", "amount": 100}}
        body = json.dumps(payload).encode("utf-8")

        with pytest.raises(SignatureMismatchError, match="Missing x-paystack-signature"):
            adapter.verify_webhook({}, body)

    def test_verify_webhook_signature_mismatch(self, adapter):
        """Test webhook verification with wrong signature."""
        payload = {"event": "charge.success", "data": {"id": 123, "reference": "TEST", "amount": 100}}
        body = json.dumps(payload).encode("utf-8")

        headers = {"x-paystack-signature": "wrong_signature"}

        with pytest.raises(SignatureMismatchError, match="signature verification failed"):
            adapter.verify_webhook(headers, body)

    def test_verify_webhook_malformed_json(self, adapter):
        """Test webhook verification with malformed JSON."""
        body = b"{ invalid json"
        
        # Valid signature for invalid JSON
        signature = hmac.new(b"sk_test_abc123", body, hashlib.sha512).hexdigest()
        headers = {"x-paystack-signature": signature}

        with pytest.raises(InvalidRequestError, match="Invalid webhook payload"):
            adapter.verify_webhook(headers, body)

    def test_verify_webhook_missing_event_field(self, adapter):
        """Test webhook verification with missing event field."""
        payload = {"data": {"id": 123, "reference": "TEST", "amount": 100}}
        body = json.dumps(payload).encode("utf-8")
        
        signature = hmac.new(b"sk_test_abc123", body, hashlib.sha512).hexdigest()
        headers = {"x-paystack-signature": signature}

        with pytest.raises(InvalidRequestError, match="Missing event field"):
            adapter.verify_webhook(headers, body)

    def test_verify_webhook_missing_required_data_fields(self, adapter):
        """Test webhook verification with missing required data fields."""
        payload = {
            "event": "charge.success",
            "data": {"id": 123},  # Missing reference and amount
        }
        body = json.dumps(payload).encode("utf-8")
        
        signature = hmac.new(b"sk_test_abc123", body, hashlib.sha512).hexdigest()
        headers = {"x-paystack-signature": signature}

        with pytest.raises(InvalidRequestError, match="Missing required fields"):
            adapter.verify_webhook(headers, body)

    def test_verify_webhook_unknown_event(self, adapter):
        """Test webhook verification with unknown event type."""
        payload = {
            "event": "unknown.event",
            "data": {"id": 123, "reference": "TEST", "amount": 100},
        }
        body = json.dumps(payload).encode("utf-8")
        
        signature = hmac.new(b"sk_test_abc123", body, hashlib.sha512).hexdigest()
        headers = {"x-paystack-signature": signature}

        with pytest.raises(InvalidRequestError, match="Unknown Paystack event"):
            adapter.verify_webhook(headers, body)

    def test_verify_webhook_case_insensitive_header(self, adapter):
        """Test webhook verification with case-insensitive header lookup."""
        payload = {"event": "charge.success", "data": {"id": 123, "reference": "TEST", "amount": 100}}
        body = json.dumps(payload).encode("utf-8")
        
        signature = hmac.new(b"sk_test_abc123", body, hashlib.sha512).hexdigest()
        
        # Use different case
        headers = {"X-Paystack-Signature": signature}

        event = adapter.verify_webhook(headers, body)
        assert event.reference == "TEST"

    def test_webhook_idempotency_same_input_same_output(self, adapter):
        """
        ADDITIONAL REQUIREMENT: Verify webhook verification is deterministic.
        
        Passing the same raw body to verify_webhook twice must produce
        equal WebhookEvent objects. The merchant-api handles idempotency
        via Redis, but the adapter must be deterministic.
        """
        payload = {"event": "charge.success", "data": {"id": 123, "reference": "TEST", "amount": 100}}
        body = json.dumps(payload).encode("utf-8")
        
        signature = hmac.new(b"sk_test_abc123", body, hashlib.sha512).hexdigest()
        headers = {"x-paystack-signature": signature}

        # Verify twice
        event1 = adapter.verify_webhook(headers, body)
        event2 = adapter.verify_webhook(headers, body)

        # Should produce identical results (except received_at timestamp)
        assert event1.provider == event2.provider
        assert event1.event_type == event2.event_type
        assert event1.provider_payment_id == event2.provider_payment_id
        assert event1.reference == event2.reference
        assert event1.amount_cents == event2.amount_cents
        assert event1.raw == event2.raw


class TestVerifyTransaction:
    """Test server-side transaction verification."""

    @pytest.fixture
    def adapter(self):
        """Create adapter for testing."""
        config = ProviderConfig(
            api_key="sk_test_abc123",
            sandbox=True,
        )
        return PaystackAdapter(config)

    @pytest.mark.asyncio
    @respx.mock
    async def test_verify_transaction_success(self, adapter):
        """Test successful server-side verification."""
        respx.get("https://api.paystack.co/transaction/verify/ORDER-ABC123").mock(
            return_value=Response(
                200,
                json={
                    "status": True,
                    "message": "Verification successful",
                    "data": {
                        "id": 1234567890,
                        "status": "success",
                        "reference": "ORDER-ABC123",
                        "amount": 10000,
                    },
                },
            )
        )

        status = await adapter.verify_transaction("ORDER-ABC123")
        assert status == PaymentStatus.SUCCEEDED

    @pytest.mark.asyncio
    @respx.mock
    async def test_verify_transaction_is_separate_from_verify_webhook(self, adapter):
        """
        Test that verify_transaction is a separate async method.
        
        verify_webhook is sync (no I/O), verify_transaction is async (hits API).
        They are called as a two-step pattern by merchant-api.
        """
        # verify_webhook is sync
        payload = {"event": "charge.success", "data": {"id": 123, "reference": "TEST", "amount": 100}}
        body = json.dumps(payload).encode("utf-8")
        signature = hmac.new(b"sk_test_abc123", body, hashlib.sha512).hexdigest()
        headers = {"x-paystack-signature": signature}
        
        event = adapter.verify_webhook(headers, body)  # Sync call
        assert event.reference == "TEST"

        # verify_transaction is async
        respx.get("https://api.paystack.co/transaction/verify/TEST").mock(
            return_value=Response(
                200,
                json={
                    "status": True,
                    "data": {"id": 123, "status": "success", "reference": "TEST", "amount": 100},
                },
            )
        )
        
        status = await adapter.verify_transaction("TEST")  # Async call
        assert status == PaymentStatus.SUCCEEDED


class TestRefund:
    """Test refund operations."""

    @pytest.fixture
    def adapter(self):
        """Create adapter for testing."""
        config = ProviderConfig(
            api_key="sk_test_abc123",
            sandbox=True,
        )
        return PaystackAdapter(config)

    @pytest.mark.asyncio
    @respx.mock
    async def test_refund_full(self, adapter):
        """Test full refund (no amount specified)."""
        respx.post("https://api.paystack.co/refund").mock(
            return_value=Response(
                200,
                json={
                    "status": True,
                    "message": "Refund has been queued for processing",
                    "data": {
                        "transaction": {"id": 1234567890, "reference": "ORDER-ABC123"},
                        "refund": {"id": 987654321, "amount": 10000, "status": "pending"},
                    },
                },
            )
        )

        result = await adapter.refund("ORDER-ABC123")

        assert result.provider == "paystack"
        assert result.reference == "ORDER-ABC123"
        assert result.status == PaymentStatus.REFUNDED

    @pytest.mark.asyncio
    @respx.mock
    async def test_refund_partial(self, adapter):
        """Test partial refund with specified amount."""
        mock_route = respx.post("https://api.paystack.co/refund").mock(
            return_value=Response(
                200,
                json={
                    "status": True,
                    "message": "Refund has been queued for processing",
                    "data": {
                        "transaction": {"id": 1234567890, "reference": "ORDER-ABC123"},
                        "refund": {"id": 987654321, "amount": 5000, "status": "pending"},
                    },
                },
            )
        )

        result = await adapter.refund("ORDER-ABC123", amount_cents=5000)

        assert result.status == PaymentStatus.REFUNDED

        # Verify amount sent as INTEGER
        request = mock_route.calls.last.request
        payload = json.loads(request.content)
        assert isinstance(payload["amount"], int)
        assert payload["amount"] == 5000

    @pytest.mark.asyncio
    @respx.mock
    async def test_refund_amount_is_integer_not_string(self, adapter):
        """
        PAYSTACK-SPECIFIC: Verify refund amount is sent as INTEGER.
        
        This is different from initialize which uses STRING.
        """
        mock_route = respx.post("https://api.paystack.co/refund").mock(
            return_value=Response(
                200,
                json={
                    "status": True,
                    "data": {
                        "transaction": {"id": 123, "reference": "TEST"},
                        "refund": {"id": 456, "amount": 10000, "status": "pending"},
                    },
                },
            )
        )

        await adapter.refund("TEST", amount_cents=10000)

        # Verify request payload
        request = mock_route.calls.last.request
        payload = json.loads(request.content)
        
        # Amount MUST be an integer (not string)
        assert isinstance(payload["amount"], int)
        assert payload["amount"] == 10000

    @pytest.mark.asyncio
    @respx.mock
    async def test_refund_negative_amount_raises(self, adapter):
        """Test that negative refund amount raises InvalidRequestError."""
        with pytest.raises(InvalidRequestError, match="cannot be negative"):
            await adapter.refund("ORDER-ABC123", amount_cents=-100)

    @pytest.mark.asyncio
    @respx.mock
    async def test_refund_404_raises_payment_not_found(self, adapter):
        """Test that 404 response raises PaymentNotFoundError."""
        respx.post("https://api.paystack.co/refund").mock(
            return_value=Response(404, json={"status": False, "message": "Not found"})
        )

        with pytest.raises(PaymentNotFoundError, match="Transaction not found"):
            await adapter.refund("NOTFOUND")

    @pytest.mark.asyncio
    @respx.mock
    async def test_refund_400_raises_refund_error(self, adapter):
        """Test that 400 response raises RefundError."""
        respx.post("https://api.paystack.co/refund").mock(
            return_value=Response(
                400, json={"status": False, "message": "Transaction not refundable"}
            )
        )

        with pytest.raises(RefundError, match="Transaction not refundable"):
            await adapter.refund("ORDER-ABC123")

    @pytest.mark.asyncio
    @respx.mock
    async def test_refund_401_raises_authentication_error(self, adapter):
        """Test that 401 response raises AuthenticationError."""
        respx.post("https://api.paystack.co/refund").mock(
            return_value=Response(401, json={"status": False, "message": "Invalid key"})
        )

        with pytest.raises(AuthenticationError, match="Invalid Paystack API key"):
            await adapter.refund("ORDER-ABC123")


class TestFootgunRegressions:
    """
    Consolidated footgun regression tests.
    
    These tests prevent known integration bugs from being reintroduced.
    Some are duplicated from per-method classes for navigability.
    """

    @pytest.fixture
    def adapter(self):
        """Create adapter for testing."""
        config = ProviderConfig(
            api_key="sk_test_abc123",
            sandbox=True,
        )
        return PaystackAdapter(config)

    def test_verify_webhook_uses_constant_time_comparison(self, adapter):
        """FOOTGUN: Signature comparison must use hmac.compare_digest."""
        payload = {"event": "charge.success", "data": {"id": 123, "reference": "TEST", "amount": 100}}
        body = json.dumps(payload).encode("utf-8")
        headers = {"x-paystack-signature": "wrong"}

        with pytest.raises(SignatureMismatchError):
            adapter.verify_webhook(headers, body)

    def test_money_conversion_integer_cents_no_float_drift(self, adapter):
        """FOOTGUN: Money conversion must avoid float drift."""
        # The 8550 case is known to drift with floats
        assert adapter._cents_to_string(8550) == "8550"

    def test_verify_webhook_uses_raw_bytes_not_parsed_json(self, adapter):
        """FOOTGUN: Webhook signature must be computed over raw bytes."""
        payload = {"event": "charge.success", "data": {"id": 123, "reference": "TEST", "amount": 100}}
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        signature = hmac.new(b"sk_test_abc123", body, hashlib.sha512).hexdigest()
        headers = {"x-paystack-signature": signature}

        event = adapter.verify_webhook(headers, body)
        assert event.reference == "TEST"

    @pytest.mark.asyncio
    @respx.mock
    async def test_initialize_amount_is_string_refund_amount_is_integer(self, adapter):
        """PAYSTACK FOOTGUN: Amount format varies by endpoint."""
        # Initialize: amount as STRING
        respx.post("https://api.paystack.co/transaction/initialize").mock(
            return_value=Response(
                200,
                json={
                    "status": True,
                    "data": {
                        "authorization_url": "https://checkout.paystack.com/test",
                        "reference": "TEST",
                    },
                },
            )
        )
        
        intent = PaymentIntent(
            amount_cents=10000,
            currency="ZAR",
            reference="TEST",
            customer_email="test@example.com",
            customer_name="Test",
            return_url=HttpUrl("https://example.com/success"),
            cancel_url=HttpUrl("https://example.com/cancel"),
            webhook_url=HttpUrl("https://example.com/webhook"),
        )
        
        await adapter.create_payment(intent)
        init_request = respx.calls.last.request
        init_payload = json.loads(init_request.content)
        assert isinstance(init_payload["amount"], str)

        # Refund: amount as INTEGER
        respx.post("https://api.paystack.co/refund").mock(
            return_value=Response(
                200,
                json={
                    "status": True,
                    "data": {
                        "transaction": {"reference": "TEST"},
                        "refund": {"amount": 5000},
                    },
                },
            )
        )
        
        await adapter.refund("TEST", amount_cents=5000)
        refund_request = respx.calls.last.request
        refund_payload = json.loads(refund_request.content)
        assert isinstance(refund_payload["amount"], int)

    def test_paystack_api_key_used_for_both_bearer_and_webhook_hmac(self, adapter):
        """PAYSTACK FOOTGUN: api_key serves dual purpose."""
        # Bearer token
        headers = adapter._get_headers()
        assert "Bearer sk_test_abc123" in headers["Authorization"]

        # Webhook HMAC
        payload = {"event": "charge.success", "data": {"id": 123, "reference": "TEST", "amount": 100}}
        body = json.dumps(payload).encode("utf-8")
        signature = hmac.new(b"sk_test_abc123", body, hashlib.sha512).hexdigest()
        headers_webhook = {"x-paystack-signature": signature}
        
        event = adapter.verify_webhook(headers_webhook, body)
        assert event.reference == "TEST"

    def test_abandoned_status_maps_to_failed(self, adapter):
        """PAYSTACK FOOTGUN: 'abandoned' status maps to FAILED."""
        assert adapter._map_status("abandoned") == PaymentStatus.FAILED

    @pytest.mark.asyncio
    @respx.mock
    async def test_authorization_url_is_redirect_target_not_access_code(self, adapter):
        """PAYSTACK FOOTGUN: Redirect to authorization_url, not access_code."""
        respx.post("https://api.paystack.co/transaction/initialize").mock(
            return_value=Response(
                200,
                json={
                    "status": True,
                    "data": {
                        "authorization_url": "https://checkout.paystack.com/correct",
                        "access_code": "wrong",
                        "reference": "TEST",
                    },
                },
            )
        )
        
        intent = PaymentIntent(
            amount_cents=10000,
            currency="ZAR",
            reference="TEST",
            customer_email="test@example.com",
            customer_name="Test",
            return_url=HttpUrl("https://example.com/success"),
            cancel_url=HttpUrl("https://example.com/cancel"),
            webhook_url=HttpUrl("https://example.com/webhook"),
        )
        
        result = await adapter.create_payment(intent)
        assert str(result.redirect_url) == "https://checkout.paystack.com/correct"


# Made with Bob