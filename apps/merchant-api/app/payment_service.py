"""Payment service for managing payment operations."""

from pydantic import HttpUrl
from lekker_pay import PaymentRouter, PaymentIntent, ProviderConfig
from lekker_pay.providers.payfast import PayFastAdapter
from lekker_pay.providers.paystack import PaystackAdapter

from app.config import settings


class PaymentService:
    """Service for managing payment operations with Lekker Pay."""

    def __init__(self) -> None:
        """Initialize payment service with configured providers."""
        # Configure PayFast
        payfast_config = ProviderConfig(
            merchant_id=settings.payfast_merchant_id,
            merchant_key=settings.payfast_merchant_key,
            passphrase=settings.payfast_passphrase,
            sandbox=settings.payfast_sandbox,
        )

        # Configure Paystack
        paystack_config = ProviderConfig(
            api_key=settings.paystack_secret_key,
            sandbox=True,  # Determined by sk_test_ vs sk_live_ prefix
        )

        # Initialize router with provider configs
        self.router = PaymentRouter({
            "payfast": payfast_config,
            "paystack": paystack_config,
        })

        # Register adapters
        self.router.register_adapter("payfast", PayFastAdapter)
        self.router.register_adapter("paystack", PaystackAdapter)

    async def create_payment(
        self,
        provider: str,
        amount_cents: int,
        reference: str,
        customer_email: str,
        customer_name: str,
        return_url: str,
        cancel_url: str,
        webhook_url: str,
    ) -> dict:
        """
        Create a payment with the specified provider.
        
        Args:
            provider: Provider name (e.g., "payfast")
            amount_cents: Amount in cents
            reference: Unique order reference
            customer_email: Customer email
            customer_name: Customer name
            return_url: Success redirect URL
            cancel_url: Cancel redirect URL
            webhook_url: Webhook notification URL
            
        Returns:
            Payment result dictionary
        """
        intent = PaymentIntent(
            amount_cents=amount_cents,
            currency="ZAR",
            reference=reference,
            customer_email=customer_email,
            customer_name=customer_name,
            return_url=HttpUrl(return_url),
            cancel_url=HttpUrl(cancel_url),
            webhook_url=HttpUrl(webhook_url),
        )

        result = await self.router.create_payment(provider, intent)

        return {
            "provider": result.provider,
            "provider_payment_id": result.provider_payment_id,
            "reference": result.reference,
            "status": result.status.value,
            "redirect_url": str(result.redirect_url) if result.redirect_url else None,
        }

    def verify_webhook(self, provider: str, headers: dict[str, str], body: bytes) -> dict:
        """
        Verify webhook signature and parse event.
        
        Args:
            provider: Provider name
            headers: HTTP headers from webhook request
            body: Raw request body as bytes
            
        Returns:
            Parsed webhook event dictionary
        """
        event = self.router.verify_webhook(provider, headers, body)

        return {
            "provider": event.provider,
            "event_type": event.event_type,
            "provider_payment_id": event.provider_payment_id,
            "reference": event.reference,
            "amount_cents": event.amount_cents,
            "received_at": event.received_at.isoformat(),
        }

    async def get_payment_status(self, provider: str, provider_payment_id: str) -> str:
        """
        Get payment status from provider.
        
        Args:
            provider: Provider name
            provider_payment_id: Provider's payment ID
            
        Returns:
            Payment status string
        """
        status = await self.router.get_status(provider, provider_payment_id)
        return status.value


# Global payment service instance
payment_service = PaymentService()

# Made with Bob
