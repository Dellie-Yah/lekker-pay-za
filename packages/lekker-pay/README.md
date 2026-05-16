# Lekker Pay

Unified payment adapter library for South African payment providers.

## Supported Providers

- PayFast
- Ozow
- Yoco

## Installation

```bash
pip install lekker-pay
```

## Quick Start

```python
from lekker_pay import PaymentRouter, PaymentIntent, ProviderConfig

# Configure providers
config = {
    "payfast": ProviderConfig(
        merchant_id="10000100",
        merchant_key="46f0cd694581a",
        passphrase="jt7NOE43FZPn",
        sandbox=True
    )
}

# Initialize router
router = PaymentRouter(config)

# Create payment
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

result = await router.create_payment("payfast", intent)
# Redirect customer to result.redirect_url
```

## Documentation

See [docs/](../../docs/) for full documentation.