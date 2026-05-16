# Paystack Payment Provider

Official documentation: https://paystack.com/docs/api/

## Overview

Paystack is a Nigerian payment gateway that supports card payments, bank transfers, mobile money, and USSD. This adapter implements card payment processing with webhook notifications.

## Authentication

Paystack uses Bearer token authentication with API keys.

### Obtaining Credentials

1. Sign up at https://paystack.com/
2. Navigate to Settings → API Keys & Webhooks
3. Copy your **Secret Key** (starts with `sk_test_` for sandbox, `sk_live_` for production)
4. Copy your **Public Key** (starts with `pk_test_` for sandbox, `pk_live_` for production)

### Sandbox vs Production

- **Sandbox**: Use test keys (`sk_test_...`, `pk_test_...`)
- **Production**: Use live keys (`sk_live_...`, `pk_live_...`)

## API Endpoints

### Base URLs

- **Sandbox**: `https://api.paystack.co`
- **Production**: `https://api.paystack.co` (same URL, different keys)

### Initialize Transaction

**Endpoint**: `POST /transaction/initialize`

**Headers**:
```
Authorization: Bearer sk_test_YOUR_SECRET_KEY
Content-Type: application/json
```

**Request Body**:
```json
{
  "email": "customer@example.com",
  "amount": "10000",
  "currency": "ZAR",
  "reference": "ORDER-ABC123",
  "callback_url": "https://example.com/payment/callback",
  "metadata": {
    "custom_fields": [
      {
        "display_name": "Customer Name",
        "variable_name": "customer_name",
        "value": "John Doe"
      }
    ]
  }
}
```

**Important Notes**:
- `amount` is in **kobo** (smallest currency unit). For ZAR: 1 Rand = 100 cents
- `amount` must be a **string**, not an integer
- `reference` must be unique per transaction
- `currency` supports: NGN, GHS, ZAR, USD

**Response** (200 OK):
```json
{
  "status": true,
  "message": "Authorization URL created",
  "data": {
    "authorization_url": "https://checkout.paystack.com/abc123xyz",
    "access_code": "abc123xyz",
    "reference": "ORDER-ABC123"
  }
}
```

**Error Response** (400 Bad Request):
```json
{
  "status": false,
  "message": "Invalid email address"
}
```

### Verify Transaction

**Endpoint**: `GET /transaction/verify/:reference`

**Headers**:
```
Authorization: Bearer sk_test_YOUR_SECRET_KEY
```

**Response** (200 OK):
```json
{
  "status": true,
  "message": "Verification successful",
  "data": {
    "id": 1234567890,
    "domain": "test",
    "status": "success",
    "reference": "ORDER-ABC123",
    "amount": 10000,
    "message": null,
    "gateway_response": "Successful",
    "paid_at": "2024-01-15T10:30:00.000Z",
    "created_at": "2024-01-15T10:29:00.000Z",
    "channel": "card",
    "currency": "ZAR",
    "ip_address": "192.168.1.1",
    "metadata": {
      "custom_fields": [
        {
          "display_name": "Customer Name",
          "variable_name": "customer_name",
          "value": "John Doe"
        }
      ]
    },
    "customer": {
      "id": 123456,
      "email": "customer@example.com"
    }
  }
}
```

**Status Values**:
- `success` - Payment completed successfully
- `failed` - Payment failed
- `abandoned` - Customer abandoned payment
- `pending` - Payment is being processed

### Refund Transaction

**Endpoint**: `POST /refund`

**Headers**:
```
Authorization: Bearer sk_test_YOUR_SECRET_KEY
Content-Type: application/json
```

**Request Body**:
```json
{
  "transaction": "ORDER-ABC123",
  "amount": 5000,
  "currency": "ZAR",
  "customer_note": "Refund for order cancellation",
  "merchant_note": "Customer requested refund"
}
```

**Notes**:
- `amount` is optional. If not provided, full refund is processed
- `amount` is in kobo/cents (integer)
- Refunds can take 1-5 business days to reflect

**Response** (200 OK):
```json
{
  "status": true,
  "message": "Refund has been queued for processing",
  "data": {
    "transaction": {
      "id": 1234567890,
      "reference": "ORDER-ABC123"
    },
    "refund": {
      "id": 987654321,
      "amount": 5000,
      "currency": "ZAR",
      "status": "pending"
    }
  }
}
```

## Webhook Configuration

### Webhook URL Format

```
https://your-domain.com/webhooks/paystack
```

### Webhook Signature Verification

Paystack signs webhooks using **HMAC-SHA512**.

**Signature Header**: `x-paystack-signature`

**Verification Process**:
```python
import hmac
import hashlib

def verify_paystack_webhook(secret_key: str, signature: str, body: bytes) -> bool:
    """
    Verify Paystack webhook signature.
    
    CRITICAL: Use hmac.compare_digest() for constant-time comparison.
    """
    expected_signature = hmac.new(
        secret_key.encode('utf-8'),
        body,
        hashlib.sha512
    ).hexdigest()
    
    # MUST use constant-time comparison
    return hmac.compare_digest(expected_signature, signature)
```

### Webhook Events

Paystack sends webhooks for various events. Key events for payment processing:

#### charge.success

Sent when a payment is successful.

**Payload**:
```json
{
  "event": "charge.success",
  "data": {
    "id": 1234567890,
    "domain": "test",
    "status": "success",
    "reference": "ORDER-ABC123",
    "amount": 10000,
    "message": null,
    "gateway_response": "Successful",
    "paid_at": "2024-01-15T10:30:00.000Z",
    "created_at": "2024-01-15T10:29:00.000Z",
    "channel": "card",
    "currency": "ZAR",
    "ip_address": "192.168.1.1",
    "metadata": {
      "custom_fields": [
        {
          "display_name": "Customer Name",
          "variable_name": "customer_name",
          "value": "John Doe"
        }
      ]
    },
    "customer": {
      "id": 123456,
      "email": "customer@example.com"
    }
  }
}
```

#### charge.failed

Sent when a payment fails.

**Payload**: Same structure as `charge.success`, but `status` is `"failed"`.

#### refund.processed

Sent when a refund is completed.

**Payload**:
```json
{
  "event": "refund.processed",
  "data": {
    "transaction": {
      "id": 1234567890,
      "reference": "ORDER-ABC123"
    },
    "refund": {
      "id": 987654321,
      "amount": 5000,
      "currency": "ZAR",
      "status": "processed",
      "refunded_at": "2024-01-20T14:30:00.000Z"
    }
  }
}
```

### Webhook Best Practices

1. **Always verify signature** before processing
2. **Use constant-time comparison** (`hmac.compare_digest()`)
3. **Preserve raw body** for signature verification
4. **Implement idempotency** (check if webhook already processed)
5. **Return 200 OK** quickly (process async if needed)
6. **Log all webhooks** for debugging

## Test Cards

Paystack provides test cards for sandbox testing:

### Successful Payment
- **Card Number**: `4084084084084081`
- **CVV**: Any 3 digits
- **Expiry**: Any future date
- **PIN**: `0000`
- **OTP**: `123456`

### Failed Payment (Insufficient Funds)
- **Card Number**: `5060666666666666666`
- **CVV**: Any 3 digits
- **Expiry**: Any future date

### Failed Payment (Declined)
- **Card Number**: `5078 5078 5078 5078 12`
- **CVV**: Any 3 digits
- **Expiry**: Any future date

## Rate Limits

- **API Requests**: No official limit, but recommended max 100 requests/second
- **Webhooks**: Paystack retries failed webhooks with exponential backoff

## Error Codes

| Code | Message | Description |
|------|---------|-------------|
| 400 | Bad Request | Invalid request parameters |
| 401 | Unauthorized | Invalid or missing API key |
| 404 | Not Found | Transaction not found |
| 500 | Internal Server Error | Paystack server error |

## Special Considerations

### Currency Support

Paystack supports multiple currencies, but availability depends on your account:
- **NGN** (Nigerian Naira) - Default
- **GHS** (Ghanaian Cedi)
- **ZAR** (South African Rand)
- **USD** (US Dollar)

### Amount Format

- API expects amount as **string** in kobo/cents
- Example: R100.00 = `"10000"` (string, not integer)
- Webhook returns amount as **integer** in kobo/cents

### Reference Uniqueness

- Each transaction must have a unique `reference`
- Attempting to reuse a reference will fail
- Use format like `ORDER-{UUID}` or `ORDER-{timestamp}-{random}`

### Metadata

- Use `metadata.custom_fields` for additional data
- Maximum 5 custom fields
- Each field has `display_name`, `variable_name`, and `value`

### Webhook Retry Logic

Paystack retries failed webhooks:
1. Immediate retry
2. 1 minute later
3. 10 minutes later
4. 1 hour later
5. 6 hours later
6. 24 hours later

Return `200 OK` to stop retries.

## Implementation Checklist

- [ ] Obtain sandbox API keys
- [ ] Implement `/transaction/initialize` for payment creation
- [ ] Implement webhook signature verification (HMAC-SHA512)
- [ ] Implement `/transaction/verify/:reference` for status checking
- [ ] Implement `/refund` for refunds
- [ ] Map Paystack statuses to `PaymentStatus` enum
- [ ] Handle amount conversion (string ↔ integer)
- [ ] Test with Paystack test cards
- [ ] Implement idempotency for webhooks
- [ ] Add comprehensive test suite (≥95% coverage)

## Example Usage

```python
from lekker_pay import PaymentRouter, PaymentIntent, ProviderConfig
from lekker_pay.providers.paystack import PaystackAdapter

# Configure Paystack
config = ProviderConfig(
    api_key="sk_test_YOUR_SECRET_KEY",
    webhook_secret="YOUR_WEBHOOK_SECRET",
    sandbox=True,
)

# Initialize router
router = PaymentRouter({"paystack": config})
router.register_adapter("paystack", PaystackAdapter)

# Create payment
intent = PaymentIntent(
    amount_cents=10000,  # R100.00
    currency="ZAR",
    reference="ORDER-ABC123",
    customer_email="customer@example.com",
    customer_name="John Doe",
    return_url="https://example.com/success",
    cancel_url="https://example.com/cancel",
    webhook_url="https://example.com/webhooks/paystack",
)

result = await router.create_payment("paystack", intent)
# Redirect customer to result.redirect_url

# Verify webhook
event = router.verify_webhook("paystack", request.headers, await request.body())
# Process event based on event.event_type
```

## References

- [Paystack API Documentation](https://paystack.com/docs/api/)
- [Paystack Webhooks Guide](https://paystack.com/docs/payments/webhooks/)
- [Paystack Test Cards](https://paystack.com/docs/payments/test-payments/)
- [Paystack Refunds](https://paystack.com/docs/payments/refunds/)

---

**Made with Bob** 🤖