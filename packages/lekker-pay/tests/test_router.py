"""Tests for PaymentRouter dispatch logic."""

from datetime import datetime, timezone

import pytest
from pydantic import HttpUrl
from lekker_pay.base import (
    BasePaymentAdapter,
    PaymentIntent,
    PaymentResult,
    PaymentStatus,
    ProviderConfig,
    WebhookEvent,
)
from lekker_pay.errors import InvalidRequestError
from lekker_pay.router import PaymentRouter
from typing import Mapping


class MockAdapter(BasePaymentAdapter):
    """Mock adapter for testing router dispatch."""
    
    provider_name = "mock"
    
    def __init__(self, config: ProviderConfig) -> None:
        self.config = config
        self.create_payment_called = False
        self.get_status_called = False
        self.verify_webhook_called = False
        self.refund_called = False
    
    async def create_payment(self, intent: PaymentIntent) -> PaymentResult:
        self.create_payment_called = True
        return PaymentResult(
            provider="mock",
            provider_payment_id="mock-123",
            reference=intent.reference,
            status=PaymentStatus.PENDING,
            redirect_url=HttpUrl("https://mock.example.com/checkout"),
            raw={"id": "mock-123", "status": "pending"},
        )
    
    async def get_status(self, provider_payment_id: str) -> PaymentStatus:
        self.get_status_called = True
        return PaymentStatus.SUCCEEDED
    
    def verify_webhook(self, headers: Mapping[str, str], body: bytes) -> WebhookEvent:
        self.verify_webhook_called = True
        return WebhookEvent(
            provider="mock",
            event_type="payment.succeeded",
            provider_payment_id="mock-123",
            reference="TEST-001",
            amount_cents=10000,
            raw={"test": "data"},
            received_at=datetime.now(timezone.utc),
        )
    
    async def refund(
        self, provider_payment_id: str, amount_cents: int | None = None
    ) -> PaymentResult:
        self.refund_called = True
        return PaymentResult(
            provider="mock",
            provider_payment_id=provider_payment_id,
            reference="TEST-001",
            status=PaymentStatus.REFUNDED,
            redirect_url=None,
            raw={"refund_amount": amount_cents or 10000},
        )


@pytest.fixture
def router() -> PaymentRouter:
    """Create router with mock provider."""
    config = ProviderConfig(api_key="test", sandbox=True)
    router = PaymentRouter({"mock": config})
    router.register_adapter("mock", MockAdapter)
    return router


@pytest.fixture
def sample_intent() -> PaymentIntent:
    """Sample payment intent."""
    return PaymentIntent(
        amount_cents=10000,
        currency="ZAR",
        reference="TEST-001",
        customer_email="test@example.com",
        customer_name="Test User",
        return_url=HttpUrl("https://example.com/return"),
        cancel_url=HttpUrl("https://example.com/cancel"),
        webhook_url=HttpUrl("https://example.com/webhook"),
    )


class TestRouterRegistration:
    """Test adapter registration."""
    
    def test_register_adapter(self) -> None:
        """Test registering an adapter class."""
        router = PaymentRouter({})
        router.register_adapter("test", MockAdapter)
        assert "test" in router._adapter_classes
    
    def test_unregistered_provider_raises(self) -> None:
        """Test accessing unregistered provider raises error."""
        config = ProviderConfig(api_key="test")
        router = PaymentRouter({"unknown": config})
        
        with pytest.raises(InvalidRequestError, match="not registered"):
            router._get_adapter("unknown")
    
    def test_unconfigured_provider_raises(self) -> None:
        """Test accessing unconfigured provider raises error."""
        router = PaymentRouter({})
        router.register_adapter("test", MockAdapter)
        
        with pytest.raises(InvalidRequestError, match="not configured"):
            router._get_adapter("test")
    
    def test_unregistered_provider_error_message(self) -> None:
        """Test error message lists available providers."""
        config = ProviderConfig(api_key="test")
        router = PaymentRouter({"mock": config})
        router.register_adapter("mock", MockAdapter)
        
        with pytest.raises(InvalidRequestError, match="Available providers: mock"):
            router._get_adapter("unknown")


class TestRouterDispatch:
    """Test router dispatches to correct adapter."""
    
    async def test_create_payment_dispatch(
        self, router: PaymentRouter, sample_intent: PaymentIntent
    ) -> None:
        """Test create_payment dispatches to adapter."""
        result = await router.create_payment("mock", sample_intent)
        
        assert result.provider_payment_id == "mock-123"
        assert result.status == PaymentStatus.PENDING
        
        adapter = router._adapters["mock"]
        assert isinstance(adapter, MockAdapter)
        assert adapter.create_payment_called
    
    async def test_get_status_dispatch(self, router: PaymentRouter) -> None:
        """Test get_status dispatches to adapter."""
        status = await router.get_status("mock", "mock-123")
        
        assert status == PaymentStatus.SUCCEEDED
        
        adapter = router._adapters["mock"]
        assert isinstance(adapter, MockAdapter)
        assert adapter.get_status_called
    
    def test_verify_webhook_dispatch(self, router: PaymentRouter) -> None:
        """Test verify_webhook dispatches to adapter."""
        event = router.verify_webhook("mock", {}, b"test")
        
        assert event.provider_payment_id == "mock-123"
        assert event.event_type == "payment.succeeded"
        
        adapter = router._adapters["mock"]
        assert isinstance(adapter, MockAdapter)
        assert adapter.verify_webhook_called
    
    async def test_refund_dispatch(self, router: PaymentRouter) -> None:
        """Test refund dispatches to adapter."""
        result = await router.refund("mock", "mock-123", 5000)
        
        assert result.status == PaymentStatus.REFUNDED
        assert result.raw["refund_amount"] == 5000
        
        adapter = router._adapters["mock"]
        assert isinstance(adapter, MockAdapter)
        assert adapter.refund_called


class TestAdapterCaching:
    """Test adapter instance caching."""
    
    async def test_adapter_reused_across_calls(
        self, router: PaymentRouter, sample_intent: PaymentIntent
    ) -> None:
        """Test same adapter instance is reused."""
        await router.create_payment("mock", sample_intent)
        first_adapter = router._adapters["mock"]
        
        await router.get_status("mock", "mock-123")
        second_adapter = router._adapters["mock"]
        
        assert first_adapter is second_adapter

# Made with Bob
