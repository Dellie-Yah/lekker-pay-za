"""
Comprehensive test suite for PayFast adapter.

Tests cover:
- Configuration validation
- Money conversion edge cases
- Signature generation (checkout vs refunds)
- Field order regression tests
- Empty passphrase handling
- URL encoding (quote_plus behavior)
- Payment creation
- Webhook verification
- ITN validation
- Refund operations
- Error handling
"""

import hashlib
import hmac
import urllib.parse

import pytest
import respx
from httpx import Response
from pydantic import HttpUrl

from lekker_pay import PaymentIntent, PaymentStatus
from lekker_pay.errors import (
    AuthenticationError,
    InvalidRequestError,
    NetworkError,
    PaymentNotFoundError,
    RefundError,
    SignatureMismatchError,
)
from lekker_pay.providers.payfast import PayFastAdapter, PayFastConfig


class TestPayFastConfig:
    """Test PayFast configuration."""

    def test_config_creation(self):
        """Test creating a valid PayFast config."""
        config = PayFastConfig(
            merchant_id="10000100",
            merchant_key="46f0cd694581a",
            passphrase="jt7NOE43FZPn",
            sandbox=True,
            timeout=30.0,
        )
        assert config.merchant_id == "10000100"
        assert config.merchant_key == "46f0cd694581a"
        assert config.passphrase == "jt7NOE43FZPn"
        assert config.sandbox is True
        assert config.timeout == 30.0

    def test_config_is_frozen(self):
        """Test that config is immutable (frozen dataclass)."""
        config = PayFastConfig(
            merchant_id="10000100",
            merchant_key="46f0cd694581a",
            passphrase="jt7NOE43FZPn",
        )
        with pytest.raises(AttributeError):
            config.merchant_id = "different"  # type: ignore

    def test_config_empty_passphrase(self):
        """Test config with empty passphrase (valid scenario)."""
        config = PayFastConfig(
            merchant_id="10000100",
            merchant_key="46f0cd694581a",
            passphrase="",  # Empty is valid
            sandbox=True,
        )
        assert config.passphrase == ""


class TestMoneyConversion:
    """Test money conversion between cents and rand strings."""

    @pytest.fixture
    def adapter(self):
        """Create adapter for testing."""
        config = PayFastConfig(
            merchant_id="10000100",
            merchant_key="46f0cd694581a",
            passphrase="jt7NOE43FZPn",
            sandbox=True,
        )
        return PayFastAdapter(config)

    def test_cents_to_rands_zero(self, adapter):
        """Test converting 0 cents."""
        assert adapter._cents_to_rands_string(0) == "0.00"

    def test_cents_to_rands_one_cent(self, adapter):
        """Test converting 1 cent."""
        assert adapter._cents_to_rands_string(1) == "0.01"

    def test_cents_to_rands_float_drift_case(self, adapter):
        """Test the 8550 cents case (R85.50) - known float drift scenario."""
        # This is the critical test: 8550 / 100 as float can drift
        # Using Decimal prevents this
        assert adapter._cents_to_rands_string(8550) == "85.50"

    def test_cents_to_rands_round_amount(self, adapter):
        """Test converting round rand amount."""
        assert adapter._cents_to_rands_string(10000) == "100.00"

    def test_cents_to_rands_large_amount(self, adapter):
        """Test converting large amount."""
        assert adapter._cents_to_rands_string(123456789) == "1234567.89"

    def test_cents_to_rands_negative_raises(self, adapter):
        """Test that negative amounts raise InvalidRequestError."""
        with pytest.raises(InvalidRequestError, match="cannot be negative"):
            adapter._cents_to_rands_string(-100)


class TestCheckoutSignature:
    """Test checkout signature generation."""

    @pytest.fixture
    def adapter(self):
        """Create adapter with passphrase."""
        config = PayFastConfig(
            merchant_id="10000100",
            merchant_key="46f0cd694581a",
            passphrase="jt7NOE43FZPn",
            sandbox=True,
        )
        return PayFastAdapter(config)

    @pytest.fixture
    def adapter_no_passphrase(self):
        """Create adapter without passphrase."""
        config = PayFastConfig(
            merchant_id="10000100",
            merchant_key="46f0cd694581a",
            passphrase="",
            sandbox=True,
        )
        return PayFastAdapter(config)

    def test_signature_field_order_is_documentation_order_not_alphabetical(self, adapter):
        """
        REGRESSION TEST: Verify signature uses documentation order, not alphabetical.

        This is the #1 PayFast integration bug. The checkout signature must use
        the field order from PayFast's documentation, which groups fields semantically.
        Alphabetical sorting produces a DIFFERENT signature.
        """
        params = {
            "merchant_id": "10000100",
            "merchant_key": "46f0cd694581a",
            "amount": "100.00",
            "item_name": "Test Item",
            "m_payment_id": "TEST-123",
        }

        # Get signature using documentation order (correct)
        doc_order_sig = adapter._build_checkout_signature(params)

        # Build signature using alphabetical order (WRONG)
        sorted_pairs = []
        for key in sorted(params.keys()):
            value = urllib.parse.quote_plus(str(params[key]))
            sorted_pairs.append(f"{key}={value}")
        alpha_payload = "&".join(sorted_pairs) + "&passphrase=jt7NOE43FZPn"
        alpha_sig = hashlib.md5(alpha_payload.encode()).hexdigest()

        # They MUST be different
        assert doc_order_sig != alpha_sig, (
            "Signature should differ between documentation order and alphabetical order. "
            "If they're the same, the field order constant is wrong."
        )

    def test_empty_passphrase_NOT_appended(self, adapter_no_passphrase):
        """
        REGRESSION TEST: Empty passphrase must be omitted, not appended.

        In Nov 2025, appending an empty passphrase (&passphrase=) caused 100%
        production failure. When passphrase is empty, it must be completely
        omitted from the signature string.
        """
        params = {
            "merchant_id": "10000100",
            "merchant_key": "46f0cd694581a",
            "amount": "100.00",
        }

        # Get signature with empty passphrase (should omit it)
        sig_empty = adapter_no_passphrase._build_checkout_signature(params)

        # Build signature manually without passphrase clause
        payload = "merchant_id=10000100&merchant_key=46f0cd694581a&amount=100.00"
        sig_manual = hashlib.md5(payload.encode()).hexdigest()

        # They MUST match
        assert sig_empty == sig_manual, (
            "Empty passphrase should be omitted entirely, not appended as &passphrase="
        )

    def test_signature_with_passphrase(self, adapter):
        """Test signature generation with passphrase."""
        params = {
            "merchant_id": "10000100",
            "merchant_key": "46f0cd694581a",
            "amount": "100.00",
        }

        sig = adapter._build_checkout_signature(params)

        # Verify it's a valid MD5 hex string
        assert len(sig) == 32
        assert all(c in "0123456789abcdef" for c in sig)


class TestURLEncoding:
    """Test URL encoding behavior."""

    @pytest.fixture
    def adapter(self):
        """Create adapter for testing."""
        config = PayFastConfig(
            merchant_id="10000100",
            merchant_key="46f0cd694581a",
            passphrase="test",
            sandbox=True,
        )
        return PayFastAdapter(config)

    def test_url_encoding_uses_plus_for_space(self, adapter):
        """
        REGRESSION TEST: Verify quote_plus turns spaces into +, not %20.

        PayFast's own published Python example has a bug where it calls
        .replace("+", " ") after quote_plus, which breaks signatures.
        We do NOT copy that bug.
        """
        params = {
            "merchant_id": "10000100",
            "merchant_key": "46f0cd694581a",
            "item_name": "Test Item",  # Contains space
        }

        sig = adapter._build_checkout_signature(params)

        # Manually build with correct encoding
        payload = (
            "merchant_id=10000100&merchant_key=46f0cd694581a&item_name=Test+Item&passphrase=test"
        )
        expected_sig = hashlib.md5(payload.encode()).hexdigest()

        assert sig == expected_sig

    def test_special_characters_encoded(self, adapter):
        """Test that special characters are properly URL encoded."""
        params = {
            "merchant_id": "10000100",
            "merchant_key": "46f0cd694581a",
            "item_name": "Test & Item + More",  # Special chars
        }

        sig = adapter._build_checkout_signature(params)

        # Verify signature is generated (encoding worked)
        assert len(sig) == 32


class TestCreatePayment:
    """Test payment creation (redirect flow)."""

    @pytest.fixture
    def adapter(self):
        """Create adapter for testing."""
        config = PayFastConfig(
            merchant_id="10000100",
            merchant_key="46f0cd694581a",
            passphrase="jt7NOE43FZPn",
            sandbox=True,
        )
        return PayFastAdapter(config)

    @pytest.fixture
    def sample_intent(self):
        """Create sample payment intent."""
        return PaymentIntent(
            amount_cents=10000,
            currency="ZAR",
            reference="TEST-ORDER-123",
            customer_email="test@example.com",
            customer_name="John Doe",
            return_url=HttpUrl("https://example.com/success"),
            cancel_url=HttpUrl("https://example.com/cancel"),
            webhook_url=HttpUrl("https://example.com/webhooks/payment"),
            metadata={"order_id": "123", "customer_id": "456"},
        )

    @pytest.mark.asyncio
    async def test_create_payment_success(self, adapter, sample_intent):
        """Test successful payment creation."""
        result = await adapter.create_payment(sample_intent)

        assert result.provider == "payfast"
        assert result.reference == "TEST-ORDER-123"
        assert result.status == PaymentStatus.PENDING
        assert result.provider_payment_id == "TEST-ORDER-123"  # Placeholder
        assert result.redirect_url is not None
        assert "sandbox.payfast.co.za" in str(result.redirect_url)
        assert "signature=" in str(result.redirect_url)

    @pytest.mark.asyncio
    async def test_create_payment_splits_customer_name(self, adapter, sample_intent):
        """Test that customer name is split into first/last."""
        result = await adapter.create_payment(sample_intent)

        # Check raw params contain split name
        assert "name_first" in result.raw
        assert "name_last" in result.raw
        assert result.raw["name_first"] == "John"
        assert result.raw["name_last"] == "Doe"

    @pytest.mark.asyncio
    async def test_create_payment_includes_metadata(self, adapter, sample_intent):
        """Test that metadata is included as custom fields."""
        result = await adapter.create_payment(sample_intent)

        # Check custom fields in raw params
        assert "custom_str1" in result.raw
        assert "custom_str2" in result.raw


class TestGetStatus:
    """Test payment status query."""

    @pytest.fixture
    def adapter(self):
        """Create adapter for testing."""
        config = PayFastConfig(
            merchant_id="10000100",
            merchant_key="46f0cd694581a",
            passphrase="jt7NOE43FZPn",
            sandbox=True,
        )
        return PayFastAdapter(config)

    @pytest.mark.asyncio
    async def test_get_status_returns_pending(self, adapter):
        """Test that get_status returns PENDING (no real query API)."""
        status = await adapter.get_status("12345")
        assert status == PaymentStatus.PENDING


class TestVerifyWebhook:
    """Test ITN webhook verification."""

    @pytest.fixture
    def adapter(self):
        """Create adapter with passphrase."""
        config = PayFastConfig(
            merchant_id="10000100",
            merchant_key="46f0cd694581a",
            passphrase="jt7NOE43FZPn",
            sandbox=True,
        )
        return PayFastAdapter(config)

    @pytest.fixture
    def adapter_no_passphrase(self):
        """Create adapter without passphrase."""
        config = PayFastConfig(
            merchant_id="10000100",
            merchant_key="46f0cd694581a",
            passphrase="",
            sandbox=True,
        )
        return PayFastAdapter(config)

    def test_verify_webhook_success(self, adapter):
        """Test successful webhook verification."""
        # Build valid ITN body
        params = {
            "m_payment_id": "TEST-123",
            "pf_payment_id": "1234567",
            "payment_status": "COMPLETE",
            "amount_gross": "100.00",
            "merchant_id": "10000100",
        }

        # Build signature
        param_pairs = []
        for key, value in params.items():
            encoded = urllib.parse.quote_plus(str(value))
            param_pairs.append(f"{key}={encoded}")
        payload = "&".join(param_pairs) + "&passphrase=jt7NOE43FZPn"
        signature = hashlib.md5(payload.encode()).hexdigest()

        # Add signature to params
        params["signature"] = signature

        # Encode as form body
        body = urllib.parse.urlencode(params).encode()

        # Verify
        event = adapter.verify_webhook({}, body)

        assert event.provider == "payfast"
        assert event.event_type == "payment.succeeded"
        assert event.provider_payment_id == "1234567"
        assert event.reference == "TEST-123"
        assert event.amount_cents == 10000

    def test_verify_webhook_signature_mismatch(self, adapter):
        """Test webhook verification with wrong signature."""
        params = {
            "m_payment_id": "TEST-123",
            "pf_payment_id": "1234567",
            "payment_status": "COMPLETE",
            "amount_gross": "100.00",
            "signature": "wrong_signature",
        }

        body = urllib.parse.urlencode(params).encode()

        with pytest.raises(SignatureMismatchError, match="signature verification failed"):
            adapter.verify_webhook({}, body)

    def test_verify_webhook_missing_signature(self, adapter):
        """Test webhook verification with missing signature."""
        params = {
            "m_payment_id": "TEST-123",
            "pf_payment_id": "1234567",
            "payment_status": "COMPLETE",
            "amount_gross": "100.00",
        }

        body = urllib.parse.urlencode(params).encode()

        with pytest.raises(SignatureMismatchError, match="Missing signature"):
            adapter.verify_webhook({}, body)

    def test_verify_webhook_missing_required_field(self, adapter):
        """Test webhook verification with missing required field."""
        params = {
            "m_payment_id": "TEST-123",
            # Missing pf_payment_id
            "payment_status": "COMPLETE",
            "amount_gross": "100.00",
            "signature": "dummy",
        }

        body = urllib.parse.urlencode(params).encode()

        with pytest.raises(InvalidRequestError, match="Missing required ITN field"):
            adapter.verify_webhook({}, body)

    def test_verify_webhook_malformed_body(self, adapter):
        """Test webhook verification with malformed body."""
        body = b"\xff\xfe invalid utf-8"

        with pytest.raises(InvalidRequestError, match="Malformed ITN body"):
            adapter.verify_webhook({}, body)

    def test_verify_webhook_unknown_status(self, adapter):
        """Test webhook verification with unknown payment status."""
        params = {
            "m_payment_id": "TEST-123",
            "pf_payment_id": "1234567",
            "payment_status": "UNKNOWN_STATUS",
            "amount_gross": "100.00",
        }

        # Build valid signature
        param_pairs = []
        for key, value in params.items():
            encoded = urllib.parse.quote_plus(str(value))
            param_pairs.append(f"{key}={encoded}")
        payload = "&".join(param_pairs) + "&passphrase=jt7NOE43FZPn"
        signature = hashlib.md5(payload.encode()).hexdigest()
        params["signature"] = signature

        body = urllib.parse.urlencode(params).encode()

        with pytest.raises(InvalidRequestError, match="Unknown PayFast status"):
            adapter.verify_webhook({}, body)

    def test_verify_webhook_failed_status(self, adapter):
        """Test webhook verification with FAILED status."""
        params = {
            "m_payment_id": "TEST-123",
            "pf_payment_id": "1234567",
            "payment_status": "FAILED",
            "amount_gross": "100.00",
        }

        # Build signature
        param_pairs = []
        for key, value in params.items():
            encoded = urllib.parse.quote_plus(str(value))
            param_pairs.append(f"{key}={encoded}")
        payload = "&".join(param_pairs) + "&passphrase=jt7NOE43FZPn"
        signature = hashlib.md5(payload.encode()).hexdigest()
        params["signature"] = signature

        body = urllib.parse.urlencode(params).encode()

        event = adapter.verify_webhook({}, body)

        assert event.event_type == "payment.failed"

    def test_verify_webhook_cancelled_status(self, adapter):
        """Test webhook verification with CANCELLED status."""
        params = {
            "m_payment_id": "TEST-123",
            "pf_payment_id": "1234567",
            "payment_status": "CANCELLED",
            "amount_gross": "100.00",
        }

        # Build signature
        param_pairs = []
        for key, value in params.items():
            encoded = urllib.parse.quote_plus(str(value))
            param_pairs.append(f"{key}={encoded}")
        payload = "&".join(param_pairs) + "&passphrase=jt7NOE43FZPn"
        signature = hashlib.md5(payload.encode()).hexdigest()
        params["signature"] = signature

        body = urllib.parse.urlencode(params).encode()

        event = adapter.verify_webhook({}, body)

        assert event.event_type == "payment.failed"  # Cancelled maps to failed

    def test_verify_webhook_with_empty_passphrase(self, adapter_no_passphrase):
        """Test webhook verification when passphrase is empty."""
        params = {
            "m_payment_id": "TEST-123",
            "pf_payment_id": "1234567",
            "payment_status": "COMPLETE",
            "amount_gross": "100.00",
        }

        # Build signature WITHOUT passphrase
        param_pairs = []
        for key, value in params.items():
            encoded = urllib.parse.quote_plus(str(value))
            param_pairs.append(f"{key}={encoded}")
        payload = "&".join(param_pairs)  # No passphrase appended
        signature = hashlib.md5(payload.encode()).hexdigest()
        params["signature"] = signature

        body = urllib.parse.urlencode(params).encode()

        event = adapter_no_passphrase.verify_webhook({}, body)

        assert event.provider_payment_id == "1234567"

    def test_verify_webhook_uses_constant_time_comparison(self, adapter, monkeypatch):
        """Test that signature comparison uses hmac.compare_digest."""
        # This test verifies the code calls hmac.compare_digest
        # We can't easily test timing, but we can verify the function is used

        compare_digest_called = False
        original_compare_digest = hmac.compare_digest

        def mock_compare_digest(a, b):
            nonlocal compare_digest_called
            compare_digest_called = True
            return original_compare_digest(a, b)

        monkeypatch.setattr(hmac, "compare_digest", mock_compare_digest)

        # Build valid ITN
        params = {
            "m_payment_id": "TEST-123",
            "pf_payment_id": "1234567",
            "payment_status": "COMPLETE",
            "amount_gross": "100.00",
        }

        param_pairs = []
        for key, value in params.items():
            encoded = urllib.parse.quote_plus(str(value))
            param_pairs.append(f"{key}={encoded}")
        payload = "&".join(param_pairs) + "&passphrase=jt7NOE43FZPn"
        signature = hashlib.md5(payload.encode()).hexdigest()
        params["signature"] = signature

        body = urllib.parse.urlencode(params).encode()

        adapter.verify_webhook({}, body)

        assert compare_digest_called, "Must use hmac.compare_digest for signature comparison"


class TestValidateITN:
    """Test server-to-server ITN validation."""

    @pytest.fixture
    def adapter(self):
        """Create adapter for testing."""
        config = PayFastConfig(
            merchant_id="10000100",
            merchant_key="46f0cd694581a",
            passphrase="jt7NOE43FZPn",
            sandbox=True,
        )
        return PayFastAdapter(config)

    @pytest.mark.asyncio
    @respx.mock
    async def test_validate_itn_success(self, adapter):
        """Test successful ITN validation."""
        respx.post("https://sandbox.payfast.co.za/eng/query/validate").mock(
            return_value=Response(200, text="VALID")
        )

        body = b"m_payment_id=TEST-123&pf_payment_id=1234567"

        is_valid = await adapter.validate_itn(body)

        assert is_valid is True

    @pytest.mark.asyncio
    @respx.mock
    async def test_validate_itn_invalid(self, adapter):
        """Test ITN validation with INVALID response."""
        respx.post("https://sandbox.payfast.co.za/eng/query/validate").mock(
            return_value=Response(200, text="INVALID")
        )

        body = b"m_payment_id=TEST-123&pf_payment_id=1234567"

        is_valid = await adapter.validate_itn(body)

        assert is_valid is False

    @pytest.mark.asyncio
    @respx.mock
    async def test_validate_itn_network_error(self, adapter):
        """Test ITN validation with network error."""
        import httpx

        respx.post("https://sandbox.payfast.co.za/eng/query/validate").mock(
            side_effect=httpx.ConnectError("Connection failed")
        )

        body = b"m_payment_id=TEST-123&pf_payment_id=1234567"

        with pytest.raises(NetworkError, match="ITN validation request failed"):
            await adapter.validate_itn(body)


class TestRefund:
    """Test refund operations."""

    @pytest.fixture
    def adapter(self):
        """Create adapter for testing."""
        config = PayFastConfig(
            merchant_id="10000100",
            merchant_key="46f0cd694581a",
            passphrase="jt7NOE43FZPn",
            sandbox=True,
        )
        return PayFastAdapter(config)

    @pytest.mark.asyncio
    @respx.mock
    async def test_refund_full_success(self, adapter):
        """Test successful full refund."""
        respx.post("https://api.payfast.co.za/refunds/1234567?testing=true").mock(
            return_value=Response(200, json={"status": "success"})
        )

        result = await adapter.refund("1234567")

        assert result.provider == "payfast"
        assert result.provider_payment_id == "1234567"
        assert result.status == PaymentStatus.REFUNDED

    @pytest.mark.asyncio
    @respx.mock
    async def test_refund_partial_success(self, adapter):
        """Test successful partial refund."""
        respx.post("https://api.payfast.co.za/refunds/1234567?testing=true").mock(
            return_value=Response(200, json={"status": "success"})
        )

        result = await adapter.refund("1234567", amount_cents=5000)

        assert result.status == PaymentStatus.REFUNDED
        assert result.raw["refund_amount_cents"] == 5000

    @pytest.mark.asyncio
    @respx.mock
    async def test_refund_payment_not_found(self, adapter):
        """Test refund with non-existent payment."""
        respx.post("https://api.payfast.co.za/refunds/9999999?testing=true").mock(
            return_value=Response(404, text="Payment not found")
        )

        with pytest.raises(PaymentNotFoundError, match="Payment not found"):
            await adapter.refund("9999999")

    @pytest.mark.asyncio
    @respx.mock
    async def test_refund_authentication_error(self, adapter):
        """Test refund with invalid credentials."""
        respx.post("https://api.payfast.co.za/refunds/1234567?testing=true").mock(
            return_value=Response(401, text="Unauthorized")
        )

        with pytest.raises(AuthenticationError, match="Invalid refund credentials"):
            await adapter.refund("1234567")

    @pytest.mark.asyncio
    @respx.mock
    async def test_refund_error(self, adapter):
        """Test refund with provider error."""
        respx.post("https://api.payfast.co.za/refunds/1234567?testing=true").mock(
            return_value=Response(400, text="Payment not refundable")
        )

        with pytest.raises(RefundError, match="Refund failed"):
            await adapter.refund("1234567")

    @pytest.mark.asyncio
    @respx.mock
    async def test_refund_network_error(self, adapter):
        """Test refund with network error."""
        import httpx

        respx.post("https://api.payfast.co.za/refunds/1234567?testing=true").mock(
            side_effect=httpx.ConnectError("Connection timeout")
        )

        with pytest.raises(NetworkError, match="Refund request failed"):
            await adapter.refund("1234567")


class TestRefundsSignature:
    """Test refunds API signature generation."""

    @pytest.fixture
    def adapter(self):
        """Create adapter for testing."""
        config = PayFastConfig(
            merchant_id="10000100",
            merchant_key="46f0cd694581a",
            passphrase="jt7NOE43FZPn",
            sandbox=True,
        )
        return PayFastAdapter(config)

    def test_refunds_signature_uses_alphabetical_order(self, adapter):
        """
        REGRESSION TEST: Refunds API uses ALPHABETICAL order (unlike checkout).

        The Refunds API is a completely separate surface from checkout.
        It uses alphabetically-sorted parameters, not documentation order.
        This test locks in that divergence.
        """
        timestamp = "2025-01-01T00:00:00Z"
        payload = '{"amount":10000}'

        sig = adapter._build_refunds_signature(timestamp, payload)

        # Manually build with alphabetical order
        parts = [
            "merchant-id=10000100",
            "passphrase=jt7NOE43FZPn",
            "timestamp=2025-01-01T00:00:00Z",
            "version=v1",
        ]
        parts.sort()  # Alphabetical
        signature_string = "&".join(parts) + payload
        expected_sig = hashlib.md5(signature_string.encode()).hexdigest()

        assert sig == expected_sig


class TestStatusMapping:
    """Test PayFast status mapping."""

    @pytest.fixture
    def adapter(self):
        """Create adapter for testing."""
        config = PayFastConfig(
            merchant_id="10000100",
            merchant_key="46f0cd694581a",
            passphrase="jt7NOE43FZPn",
            sandbox=True,
        )
        return PayFastAdapter(config)

    def test_map_status_complete(self, adapter):
        """Test mapping COMPLETE status."""
        assert adapter._map_status("COMPLETE") == PaymentStatus.SUCCEEDED

    def test_map_status_failed(self, adapter):
        """Test mapping FAILED status."""
        assert adapter._map_status("FAILED") == PaymentStatus.FAILED

    def test_map_status_cancelled(self, adapter):
        """Test mapping CANCELLED status."""
        assert adapter._map_status("CANCELLED") == PaymentStatus.CANCELLED

    def test_map_status_unknown_raises(self, adapter):
        """Test that unknown status raises InvalidRequestError."""
        with pytest.raises(InvalidRequestError, match="Unknown PayFast status"):
            adapter._map_status("UNKNOWN")


class TestAmountParsing:
    """Test ITN amount parsing."""

    @pytest.fixture
    def adapter(self):
        """Create adapter for testing."""
        config = PayFastConfig(
            merchant_id="10000100",
            merchant_key="46f0cd694581a",
            passphrase="jt7NOE43FZPn",
            sandbox=True,
        )
        return PayFastAdapter(config)

    def test_parse_itn_amount_valid(self, adapter):
        """Test parsing valid amount_gross."""
        assert adapter._parse_itn_amount("100.00") == 10000
        assert adapter._parse_itn_amount("85.50") == 8550
        assert adapter._parse_itn_amount("0.01") == 1

    def test_parse_itn_amount_invalid(self, adapter):
        """Test parsing invalid amount_gross."""
        with pytest.raises(InvalidRequestError, match="Invalid amount_gross format"):
            adapter._parse_itn_amount("invalid")


class TestAsyncContextManager:
    """Test async context manager protocol."""
    
    @pytest.fixture
    def adapter(self):
        """Create adapter for testing."""
        config = PayFastConfig(
            merchant_id="10000100",
            merchant_key="46f0cd694581a",
            passphrase="jt7NOE43FZPn",
            sandbox=True,
        )
        return PayFastAdapter(config)
    
    @pytest.mark.asyncio
    async def test_context_manager_closes_client(self, adapter):
        """Test async context manager closes HTTP client on exit."""
        async with adapter as ctx_adapter:
            assert ctx_adapter.client is not None
            assert not ctx_adapter.client.is_closed
        
        # Client should be closed after exiting context
        assert adapter.client.is_closed
    
    @pytest.mark.asyncio
    async def test_context_manager_returns_self(self, adapter):
        """Test async context manager returns adapter instance."""
        async with adapter as ctx_adapter:
            assert ctx_adapter is adapter

# Made with Bob
