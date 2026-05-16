# Yoco Integration Guide

## Overview

Yoco is a modern South African payment provider with REST API and HMAC-SHA256 webhook signatures.

## Authentication

- **API Key**: Bearer token for API requests (starts with `sk_live_` or `sk_test_`)
- **Webhook Secret**: Secret for HMAC signature verification (starts with `whsec_`)

## API Endpoints

### Sandbox
- Base URL: `https://payments.yoco.com/api`
- Checkouts: `POST /checkouts`

### Production
- Same as sandbox (use production API key)

## Payment Flow

1. **Create Checkout**: POST to `/api/checkouts` with bearer token
2. **Customer Redirect**: Redirect customer to `redirectUrl` from response
3. **Webhook**: Yoco POSTs payment events to your webhook URL
4. **Status Query**: GET `/api/checkouts/{id}` to query status

## API Request

```http
POST /api/checkouts
Authorization: Bearer sk_test_...
Content-Type: application/json

{
  "amount": 10000,
  "currency": "ZAR",
  "cancelUrl": "https://example.com/cancel",
  "successUrl": "https://example.com/success",
  "failureUrl": "https://example.com/failure",
  "metadata": {
    "reference": "ORDER-123"
  }
}
```

## Webhook Signature (HMAC-SHA256)

**CRITICAL**: Signature is computed over raw request body bytes.

```python
import hmac
import hashlib

def verify_signature(webhook_secret: str, body: bytes, signature: str) -> bool:
    expected = hmac.new(
        webhook_secret.encode(),
        body,
        hashlib.sha256
    ).hexdigest()
    
    # MUST use constant-time comparison
    return hmac.compare_digest(expected, signature)
```

**Headers**:
- `Webhook-Signature`: HMAC-SHA256 hex digest

**Body**: JSON payload (must be raw bytes for verification)

```json
{
  "type": "payment.succeeded",
  "payload": {
    "id": "ch_...",
    "status": "succeeded",
    "amount": 10000,
    "currency": "ZAR",
    "metadata": {
      "reference": "ORDER-123"
    }
  }
}
```

## Event Types

- `payment.succeeded`: Payment completed successfully
- `payment.failed`: Payment failed
- `payment.refunded`: Payment was refunded

## Status Mapping

| Yoco Status | Lekker Pay Status |
|-------------|-------------------|
| `succeeded` | `SUCCEEDED`       |
| `failed`    | `FAILED`          |
| `pending`   | `PENDING`         |
| `refunded`  | `REFUNDED`        |

## Error Handling

- **401**: Invalid API key
- **400**: Invalid request (check error message)
- **404**: Checkout not found
- **429**: Rate limit exceeded

## Refunds

```http
POST /api/refunds
Authorization: Bearer sk_test_...
Content-Type: application/json

{
  "checkoutId": "ch_...",
  "amount": 5000  // Optional, omit for full refund
}
```

## Testing

Use test API key: `sk_test_...`

Test cards:
- Success: `4242 4242 4242 4242`
- Decline: `4000 0000 0000 0002`

## References

- [Yoco API Documentation](https://developer.yoco.com/)
- [Webhook Guide](https://developer.yoco.com/webhooks)