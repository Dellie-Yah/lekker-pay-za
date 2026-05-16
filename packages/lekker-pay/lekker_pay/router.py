"""
PaymentRouter - Factory for dispatching to provider adapters.

The router maintains a registry of provider adapters and their configurations,
allowing the merchant application to work with multiple providers through a
single interface.
"""

from typing import Any

from lekker_pay.base import (
    BasePaymentAdapter,
    PaymentIntent,
    PaymentResult,
    PaymentStatus,
    ProviderConfig,
    WebhookEvent,
)
from lekker_pay.errors import InvalidRequestError


class PaymentRouter:
    """
    Factory and dispatcher for payment provider adapters.
    
    Example:
        config = {
            "payfast": ProviderConfig(
                merchant_id="10000100",
                merchant_key="46f0cd694581a",
                passphrase="jt7NOE43FZPn",
                sandbox=True
            ),
            "yoco": ProviderConfig(
                api_key="sk_test_...",
                webhook_secret="whsec_...",
                sandbox=True
            )
        }
        
        router = PaymentRouter(config)
        
        # Create payment with specific provider
        result = await router.create_payment("payfast", intent)
        
        # Verify webhook (router auto-detects provider)
        event = router.verify_webhook("payfast", headers, body)
    """

    def __init__(self, provider_configs: dict[str, ProviderConfig]) -> None:
        """
        Initialize router with provider configurations.
        
        Args:
            provider_configs: Mapping of provider name to configuration
        """
        self._configs = provider_configs
        self._adapters: dict[str, BasePaymentAdapter] = {}
        self._adapter_classes: dict[str, type[BasePaymentAdapter]] = {}

    def register_adapter(
        self, provider_name: str, adapter_class: type[BasePaymentAdapter]
    ) -> None:
        """
        Register a provider adapter class.
        
        Args:
            provider_name: Provider identifier (e.g., "payfast")
            adapter_class: Adapter class (not instance)
            
        Example:
            router.register_adapter("payfast", PayFastAdapter)
        """
        self._adapter_classes[provider_name] = adapter_class

    def _get_adapter(self, provider_name: str) -> BasePaymentAdapter:
        """
        Get or create adapter instance for a provider.
        
        Args:
            provider_name: Provider identifier
            
        Returns:
            Adapter instance
            
        Raises:
            InvalidRequestError: Provider not configured or not registered
        """
        if provider_name not in self._adapters:
            if provider_name not in self._adapter_classes:
                raise InvalidRequestError(
                    f"Provider '{provider_name}' not registered. "
                    f"Available providers: {', '.join(self._adapter_classes.keys())}"
                )

            if provider_name not in self._configs:
                raise InvalidRequestError(
                    f"Provider '{provider_name}' not configured. "
                    f"Configured providers: {', '.join(self._configs.keys())}"
                )

            adapter_class = self._adapter_classes[provider_name]
            config = self._configs[provider_name]
            self._adapters[provider_name] = adapter_class(config)

        return self._adapters[provider_name]

    async def create_payment(
        self, provider_name: str, intent: PaymentIntent
    ) -> PaymentResult:
        """
        Create payment with specified provider.
        
        Args:
            provider_name: Provider to use (e.g., "payfast")
            intent: Payment request
            
        Returns:
            Payment result with redirect URL or payment details
            
        Example:
            result = await router.create_payment("payfast", intent)
            # Redirect customer to result.redirect_url
        """
        adapter = self._get_adapter(provider_name)
        return await adapter.create_payment(intent)

    async def get_status(self, provider_name: str, provider_payment_id: str) -> PaymentStatus:
        """
        Query payment status from provider.
        
        Args:
            provider_name: Provider identifier
            provider_payment_id: Provider's payment ID
            
        Returns:
            Current payment status
        """
        adapter = self._get_adapter(provider_name)
        return await adapter.get_status(provider_payment_id)

    def verify_webhook(
        self, provider_name: str, headers: dict[str, str], body: bytes
    ) -> WebhookEvent:
        """
        Verify webhook signature and parse event.
        
        Args:
            provider_name: Provider identifier
            headers: HTTP headers from webhook request
            body: Raw request body as bytes
            
        Returns:
            Verified webhook event
            
        Raises:
            SignatureMismatchError: Signature verification failed
        """
        adapter = self._get_adapter(provider_name)
        return adapter.verify_webhook(headers, body)

    async def refund(
        self,
        provider_name: str,
        provider_payment_id: str,
        amount_cents: int | None = None,
    ) -> PaymentResult:
        """
        Refund a payment (full or partial).
        
        Args:
            provider_name: Provider identifier
            provider_payment_id: Provider's payment ID
            amount_cents: Amount to refund in cents (None = full refund)
            
        Returns:
            Refund result
        """
        adapter = self._get_adapter(provider_name)
        return await adapter.refund(provider_payment_id, amount_cents)

    def list_providers(self) -> list[str]:
        """
        List all registered and configured providers.
        
        Returns:
            List of provider names
        """
        return [
            name
            for name in self._adapter_classes.keys()
            if name in self._configs
        ]

# Made with Bob
