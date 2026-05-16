# Ozow Integration Guide

## Overview

Ozow is a South African instant EFT payment provider using SHA512 signature verification.

## Authentication

- **Site Code**: Your Ozow site identifier
- **API Key**: Private key for API authentication
- **Private Key**: Secret key for signature generation

## API Endpoints

### Sandbox
- Payment: `https://pay.sandbox.ozow.com`

### Production
- Payment: `https://pay.ozow.com`

## Payment Flow

1. **Create Payment**: POST to Ozow with signed request
2. **Customer Redirect**: Redirect customer to Ozow payment page
3. **Notification**: Ozow POSTs payment status to your notification URL
4. **Status Query**: Optional server-to-server status check

## Signature Generation (SHA512)

Ozow uses SHA512 hash of concatenated fields in specific order:

```python
import hashlib

def generate_signature(site_code: str, country_code: str, currency_code: str,
                      amount: str, transaction_ref: str, bank_ref: str,
                      optional1: str, optional2: str, optional3: str,
                      optional4: str, optional5: str, cancel_url: str,
                      error_url: str, success_url: str, notify_url: str,
                      is_test: str, private_key: str) -> str:
    
    input_string = (
        f"{site_code}{country_code}{currency_code}{amount}"
        f"{transaction_ref}{bank_ref}{optional1}{optional2}"
        f"{optional3}{optional4}{optional5}{cancel_url}"
        f"{error_url}{success_url}{notify_url}{is_test}"
    ).lower()
    
    hash_input = input_string + private_key.lower()
    return hashlib.sha512(hash_input.encode()).hexdigest()
```

## Notification Webhook

Ozow POSTs to your notification URL with payment status:

**Parameters**:
- `SiteCode`: Your site code
- `TransactionId`: Ozow's transaction ID
- `TransactionReference`: Your reference
- `Amount`: Payment amount
- `Status`: Payment status
- `Hash`: SHA512 signature

## Status Mapping

| Ozow Status | Lekker Pay Status |
|-------------|-------------------|
| `Complete`  | `SUCCEEDED`       |
| `Cancelled` | `CANCELLED`       |
| `Error`     | `FAILED`          |
| `Pending`   | `PENDING`         |

## Testing

Sandbox mode: Set `IsTest=true` in request

## References

- [Ozow API Documentation](https://docs.ozow.com/)