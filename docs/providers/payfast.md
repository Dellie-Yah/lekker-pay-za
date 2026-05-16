# PayFast Integration Guide

## Overview

PayFast is a South African payment gateway that uses a redirect-based flow with MD5 signature verification.

## Authentication

- **Merchant ID**: Unique identifier for your PayFast account
- **Merchant Key**: Secret key for signature generation
- **Passphrase**: Additional secret for enhanced security (optional but recommended)

## API Endpoints

### Sandbox
- Payment: `https://sandbox.payfast.co.za/eng/process`
- Validation: `https://sandbox.payfast.co.za/eng/query/validate`

### Production
- Payment: `https://www.payfast.co.za/eng/process`
- Validation: `https://www.payfast.co.za/eng/query/validate`

## Payment Flow

1. **Create Payment**: POST form-encoded data to `/eng/process`
2. **Customer Redirect**: PayFast redirects customer to payment page
3. **ITN Webhook**: PayFast POSTs payment status to your webhook URL
4. **Server Validation**: Your server validates ITN by POSTing back to `/eng/query/validate`

## Signature Generation (MD5)

PayFast uses MD5 signatures over alphabetically-sorted parameters:

```python
import hashlib
from urllib.parse import urlencode

def generate_signature(data: dict, passphrase: str) -> str:
    # Remove signature field if present
    data = {k: v for k, v in data.items() if k != 'signature' and v}
    
    # Sort alphabetically and URL encode
    sorted_params = sorted(data.items())
    param_string = urlencode(sorted_params)
    
    # Append passphrase
    param_string += f"&passphrase={passphrase}"
    
    # MD5 hash
    return hashlib.md5(param_string.encode()).hexdigest()
```

## ITN (Instant Transaction Notification)

PayFast sends a POST request to your webhook URL with payment details:

**Headers**: `Content-Type: application/x-www-form-urlencoded`

**Body Parameters**:
- `m_payment_id`: Your reference
- `pf_payment_id`: PayFast's payment ID
- `payment_status`: `COMPLETE`, `FAILED`, or `CANCELLED`
- `amount_gross`: Payment amount (string, e.g., "100.00")
- `signature`: MD5 signature

**Verification Steps**:
1. Verify signature matches (constant-time comparison)
2. Verify payment status
3. POST data back to `/eng/query/validate` to confirm authenticity
4. Check response is "VALID"

## Status Mapping

| PayFast Status | Lekker Pay Status |
|----------------|-------------------|
| `COMPLETE`     | `SUCCEEDED`       |
| `FAILED`       | `FAILED`          |
| `CANCELLED`    | `CANCELLED`       |

## Error Handling

- **400**: Invalid request parameters
- **401**: Invalid merchant credentials
- **500**: PayFast server error

## Testing

Use sandbox credentials:
- Merchant ID: `10000100`
- Merchant Key: `46f0cd694581a`
- Passphrase: `jt7NOE43FZPn`

Test card: Any valid card number in sandbox mode

## References

- [PayFast API Documentation](https://developers.payfast.co.za/)
- [ITN Guide](https://developers.payfast.co.za/docs#instant_transaction_notification)