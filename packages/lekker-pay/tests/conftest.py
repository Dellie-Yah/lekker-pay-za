"""
Pytest configuration and shared fixtures for lekker-pay tests.
"""

import pytest
from datetime import datetime, timezone
from pydantic import HttpUrl

from lekker_pay import PaymentIntent, ProviderConfig


@pytest.fixture
def sample_config() -> ProviderConfig:
    """Sample provider configuration for testing."""
    return ProviderConfig(
        merchant_id="10000100",
        merchant_key="46f0cd694581a",
        passphrase="jt7NOE43FZPn",
        sandbox=True,
    )


@pytest.fixture
def sample_intent() -> PaymentIntent:
    """Sample payment intent for testing."""
    return PaymentIntent(
        amount_cents=10000,  # R100.00
        currency="ZAR",
        reference="TEST-ORDER-123",
        customer_email="test@example.com",
        customer_name="Test Customer",
        return_url=HttpUrl("https://example.com/success"),
        cancel_url=HttpUrl("https://example.com/cancel"),
        webhook_url=HttpUrl("https://example.com/webhooks/payment"),
        metadata={"order_id": "123", "customer_id": "456"},
    )


@pytest.fixture
def utc_now() -> datetime:
    """Current UTC datetime for testing."""
    return datetime.now(timezone.utc)

# Made with Bob
