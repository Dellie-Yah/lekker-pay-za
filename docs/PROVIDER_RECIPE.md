# Provider Adapter Recipe

This document provides a step-by-step recipe for implementing new payment provider adapters for Lekker Pay. Follow this pattern to ensure consistency, security, and maintainability across all provider implementations.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [File Structure](#file-structure)
3. [Implementation Steps](#implementation-steps)
4. [Critical Security Rules](#critical-security-rules)
5. [Testing Requirements](#testing-requirements)
6. [Documentation Requirements](#documentation-requirements)
7. [Quality Gates](#quality-gates)

## Prerequisites

Before implementing a new provider adapter:

1. **Read the provider's API documentation thoroughly**
2. **Obtain sandbox/test credentials**
3. **Understand the provider's webhook signature verification method**
4. **Identify if the provider has a two-step webhook pattern** (webhook notification + server-side verification)
5. **Review the PayFast adapter** ([`payfast.py`](../packages/lekker-pay/lekker_pay/providers/payfast.py)) as the reference implementation

## File Structure

```
packages/lekker-pay/
├── lekker_pay/
│   └── providers/
│       ├── __init__.py          # Export new adapter
│       └── newprovider.py       # New adapter implementation
├── tests/
│   └── test_newprovider.py      # Comprehensive test suite
└── docs/
    └── providers/
        └── newprovider.md       # Provider-specific documentation
```

## Implementation Steps

### Step 1: Use the Generic ProviderConfig

Lekker Pay uses **one** configuration model — `ProviderConfig` in [`base.py`](../packages/lekker-pay/lekker_pay/base.py). It has every field any provider could need; supply only the ones your provider uses and leave the rest at their `None` defaults.

```python
from lekker_pay.base import ProviderConfig

# PayFast uses:
config = ProviderConfig(
    merchant_id="10000100",
    merchant_key="46f0cd694581a",
    passphrase="",          # empty for sandbox without passphrase
    sandbox=True,
)

# Paystack uses:
config = ProviderConfig(
    api_key="sk_test_...",  # the Paystack secret key
    sandbox=True,
)

# Yoco would use:
config = ProviderConfig(
    api_key="sk_test_...",
    webhook_secret="whsec_...",
    sandbox=True,
)
```

Do **not** create a per-provider config dataclass or Pydantic model. The generic `ProviderConfig` is the single source of truth for adapter configuration. This keeps `payment_service.py` provider-agnostic and the SaaS migration path clean — each tenant's stored credentials are one Pydantic shape, not N shapes.

### Step 2: Implement BasePaymentAdapter

```python
from lekker_pay.base import BasePaymentAdapter, PaymentIntent, PaymentResult, PaymentStatus, WebhookEvent, ProviderConfig
from lekker_pay.errors import *
import httpx
import hmac
from typing import ClassVar, Mapping

class NewProviderAdapter(BasePaymentAdapter):
    """Payment adapter for NewProvider."""
    
    provider_name: ClassVar[str] = "newprovider"
    
    def __init__(self, config: ProviderConfig) -> None:
        """Initialize adapter with configuration."""
        # Validate required config fields
        if not config.api_key:
            raise ValueError("api_key is required")
        if not config.webhook_secret:
            raise ValueError("webhook_secret is required")
            
        self.config = config
        self.client = httpx.AsyncClient(
            base_url=self._get_base_url(),
            headers={"Authorization": f"Bearer {config.api_key}"},
            timeout=30.0,
        )
    
    def _get_base_url(self) -> str:
        """Get API base URL based on sandbox flag."""
        if self.config.base_url:
            return self.config.base_url
        return (
            "https://sandbox.newprovider.com/api/v1"
            if self.config.sandbox
            else "https://api.newprovider.com/v1"
        )
    
    async def create_payment(self, intent: PaymentIntent) -> PaymentResult:
        """Create a new payment."""
        # Implementation details...
        pass
    
    async def get_status(self, provider_payment_id: str) -> PaymentStatus:
        """Get payment status."""
        # Implementation details...
        pass
    
    def verify_webhook(self, headers: Mapping[str, str], body: bytes) -> WebhookEvent:
        """Verify webhook signature and parse event."""
        # CRITICAL: Use constant-time comparison
        # Implementation details...
        pass
    
    async def refund(
        self, provider_payment_id: str, amount_cents: int | None = None
    ) -> PaymentResult:
        """Refund a payment."""
        # Implementation details...
        pass
    
    async def __aenter__(self) -> "NewProviderAdapter":
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, *args: object) -> None:
        """Async context manager exit - close HTTP client."""
        await self.client.aclose()
```

### Step 3: Implement Money Conversion Helpers

```python
def _cents_to_provider_format(self, amount_cents: int) -> str:
    """
    Convert integer cents to provider's expected format.
    
    CRITICAL: Never use floats for intermediate calculations.
    
    Args:
        amount_cents: Amount in cents (e.g., 10000 = R100.00)
        
    Returns:
        Formatted string (e.g., "100.00")
    """
    if amount_cents < 0:
        raise ValueError("amount_cents must be non-negative")
    
    rands = amount_cents // 100
    cents = amount_cents % 100
    return f"{rands}.{cents:02d}"

def _provider_format_to_cents(self, amount_str: str) -> int:
    """
    Parse provider's amount format to integer cents.
    
    Args:
        amount_str: Amount string from provider (e.g., "100.00")
        
    Returns:
        Amount in cents
        
    Raises:
        InvalidRequestError: If format is invalid
    """
    try:
        # Parse as Decimal to avoid float precision issues
        from decimal import Decimal
        amount = Decimal(amount_str)
        return int(amount * 100)
    except (ValueError, ArithmeticError) as e:
        raise InvalidRequestError(
            f"Invalid amount format: {amount_str}",
            provider=self.provider_name,
        ) from e
```

### Step 4: Implement Webhook Verification

**CRITICAL RULE: Two-Step Webhook Pattern**

If the provider offers server-side webhook verification (like PayFast's ITN validation), you MUST:

1. **Keep `verify_webhook()` synchronous** - only verify signature and parse payload
2. **Create a separate async method** for server-side verification (e.g., `validate_webhook()`)
3. **NEVER fold server-side verification into `verify_webhook()`**

```python
def verify_webhook(self, headers: Mapping[str, str], body: bytes) -> WebhookEvent:
    """
    Verify webhook signature and parse event (SYNCHRONOUS).
    
    CRITICAL SECURITY:
    1. Use hmac.compare_digest() for constant-time comparison
    2. Never use == to compare signatures (timing attack vulnerability)
    3. Preserve raw bytes for signature verification
    4. If provider has server-side verification, expose it as separate async method
    """
    # Extract signature from headers
    signature_header = headers.get("x-provider-signature")
    if not signature_header:
        raise SignatureMismatchError(
            "Missing signature header",
            provider=self.provider_name,
        )
    
    # Compute expected signature
    expected_sig = hmac.new(
        self.config.webhook_secret.encode(),
        body,
        digestmod="sha256",
    ).hexdigest()
    
    # CRITICAL: Use constant-time comparison
    if not hmac.compare_digest(expected_sig, signature_header):
        raise SignatureMismatchError(
            "Signature verification failed",
            provider=self.provider_name,
        )
    
    # Parse webhook body
    try:
        import json
        data = json.loads(body.decode())
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise InvalidRequestError(
            "Malformed webhook body",
            provider=self.provider_name,
        ) from e
    
    # Map provider status to PaymentStatus
    status = self._map_webhook_status(data["status"])
    
    return WebhookEvent(
        provider=self.provider_name,
        event_type=self._map_event_type(status),
        provider_payment_id=data["payment_id"],
        reference=data["merchant_reference"],
        amount_cents=self._provider_format_to_cents(data["amount"]),
        raw=data,
        received_at=datetime.now(timezone.utc),
    )

async def validate_webhook(self, body: bytes) -> bool:
    """
    Perform server-side webhook verification (ASYNC, SEPARATE METHOD).
    
    Use this for providers that offer server-to-server verification
    (e.g., PayFast ITN validation, Ozow notification handler).
    
    This method should be called AFTER verify_webhook() succeeds.
    """
    try:
        response = await self.client.post(
            "/webhooks/validate",
            content=body,
        )
        return response.text == "VALID"
    except httpx.HTTPError as e:
        raise NetworkError(
            f"Webhook validation request failed: {e}",
            provider=self.provider_name,
        ) from e
```

### Step 5: Implement Status Mapping

```python
def _map_status(self, provider_status: str) -> PaymentStatus:
    """Map provider-specific status to unified PaymentStatus."""
    status_map = {
        "COMPLETED": PaymentStatus.SUCCEEDED,
        "PENDING": PaymentStatus.PENDING,
        "PROCESSING": PaymentStatus.PROCESSING,
        "FAILED": PaymentStatus.FAILED,
        "REFUNDED": PaymentStatus.REFUNDED,
        "CANCELLED": PaymentStatus.CANCELLED,
    }
    
    if provider_status not in status_map:
        raise InvalidRequestError(
            f"Unknown provider status: {provider_status}",
            provider=self.provider_name,
        )
    
    return status_map[provider_status]

def _map_event_type(
    self, status: PaymentStatus
) -> Literal["payment.succeeded", "payment.failed", "payment.refunded"]:
    """Map PaymentStatus to WebhookEvent event_type."""
    if status == PaymentStatus.SUCCEEDED:
        return "payment.succeeded"
    elif status == PaymentStatus.FAILED:
        return "payment.failed"
    elif status == PaymentStatus.REFUNDED:
        return "payment.refunded"
    else:
        raise InvalidRequestError(
            f"Cannot map status {status} to event type",
            provider=self.provider_name,
        )
```

### Step 6: Error Handling Pattern

```python
async def create_payment(self, intent: PaymentIntent) -> PaymentResult:
    """Create payment with proper error handling."""
    try:
        response = await self.client.post(
            "/payments",
            json={
                "amount": self._cents_to_provider_format(intent.amount_cents),
                "reference": intent.reference,
                # ... other fields
            },
        )
        response.raise_for_status()
        data = response.json()
        
        return PaymentResult(
            provider=self.provider_name,
            provider_payment_id=data["id"],
            reference=intent.reference,
            status=self._map_status(data["status"]),
            redirect_url=HttpUrl(data["checkout_url"]),
            raw=data,
        )
        
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            raise AuthenticationError(
                "Invalid API credentials",
                provider=self.provider_name,
            ) from e
        elif e.response.status_code == 400:
            raise InvalidRequestError(
                f"Invalid payment request: {e.response.text}",
                provider=self.provider_name,
            ) from e
        else:
            raise ProviderError(
                f"Provider error: {e.response.status_code}",
                provider=self.provider_name,
            ) from e
            
    except httpx.HTTPError as e:
        raise NetworkError(
            f"Network error: {e}",
            provider=self.provider_name,
        ) from e
```

## Critical Security Rules

### 1. Webhook Signature Verification

**ALWAYS use `hmac.compare_digest()` for signature comparison:**

```python
# ✅ CORRECT - constant-time comparison
if not hmac.compare_digest(expected_sig, received_sig):
    raise SignatureMismatchError("Invalid signature")

# ❌ WRONG - timing attack vulnerability
if expected_sig != received_sig:
    raise SignatureMismatchError("Invalid signature")
```

### 2. Money Handling

**NEVER use floats for money - always use integers (cents):**

```python
# ✅ CORRECT
amount_cents = 10000  # R100.00

# ❌ WRONG - floating point precision issues
amount_rands = 100.00
```

### 3. Raw Webhook Bodies

**For HMAC verification, preserve raw bytes:**

```python
# ✅ CORRECT
@app.post("/webhooks/payment")
async def webhook(request: Request):
    body = await request.body()  # Raw bytes
    event = adapter.verify_webhook(request.headers, body)

# ❌ WRONG - body already parsed, signature will fail
@app.post("/webhooks/payment")
async def webhook(payload: dict):
    # Cannot verify signature on parsed JSON
```

### 4. Two-Step Webhook Pattern

**If provider offers server-side verification, expose it separately:**

```python
# ✅ CORRECT - two separate methods
def verify_webhook(self, headers, body) -> WebhookEvent:
    """Synchronous signature verification and parsing."""
    pass

async def validate_webhook(self, body: bytes) -> bool:
    """Async server-side verification (separate call)."""
    pass

# ❌ WRONG - folding server verification into verify_webhook
def verify_webhook(self, headers, body) -> WebhookEvent:
    """This should NOT be async or make HTTP calls."""
    # Don't do this:
    # is_valid = await self._validate_with_provider(body)
    pass
```

### 5. Reference Fidelity

**Use the merchant-supplied `reference`, never the provider's internal numeric `id`.**

The merchant matches orders by `reference` (e.g. `ORDER-ABC123`). Provider-internal IDs (Paystack's `id: 1234567890`, PayFast's `pf_payment_id`) are useful for debugging but are NOT the join key.

```python
# ✅ CORRECT
return WebhookEvent(
    provider=self.provider_name,
    reference=data["reference"],       # merchant-supplied
    provider_payment_id=str(data["id"]),  # provider-internal, for debugging
    ...
)

# ❌ WRONG - merchant's order lookup will fail
return WebhookEvent(
    reference=str(data["id"]),         # internal numeric ID — wrong join key
    ...
)
```

### 6. Full Raw Response Preservation

**`PaymentResult.raw` and `WebhookEvent.raw` store the entire provider response. Never filter.**

```python
# ✅ CORRECT
return PaymentResult(
    redirect_url=HttpUrl(data["authorization_url"]),
    raw=data,                           # everything — access_code, id, status, etc.
    ...
)

# ❌ WRONG - selective pruning makes debugging painful
return PaymentResult(
    redirect_url=HttpUrl(data["authorization_url"]),
    raw={"authorization_url": data["authorization_url"]},  # lost everything else
    ...
)
```

### 7. No Defensive Config Fallbacks

**Use only the `ProviderConfig` fields your provider's documented API actually requires.**

Do NOT add "defensive" code that prefers an alternative config field if it happens to be populated. Silent behaviour changes based on config shape are footguns.

```python
# ❌ WRONG - silent behaviour change
def _signing_key(self) -> str:
    # "if webhook_secret is set, use it, else fall back to api_key"
    return self.config.webhook_secret or self.config.api_key

# ✅ CORRECT - strict, documented use
def _signing_key(self) -> str:
    # Paystack uses the API key for both Bearer auth AND webhook HMAC.
    # This is intentional — Paystack's public API has no separate webhook secret.
    return self.config.api_key
```

If the provider later introduces a new auth shape, that's a separate change with its own tests and migration path — not a silent fallback.

### 8. Adapter Style — No Trivial Helpers

If a "helper" function is doing nothing meaningful, inline it or replace with a module-level constant.

```python
# ❌ WRONG - misleading helper
def _get_base_url(self) -> str:
    """Returns API base URL based on sandbox flag."""
    if self.config.sandbox:
        return "https://api.paystack.co"
    return "https://api.paystack.co"      # same URL — the helper is a lie

# ✅ CORRECT - constant
_BASE_URL = "https://api.paystack.co"     # same for sandbox and live
```

## Testing Requirements

### Coverage Target

**Provider adapter files MUST achieve ≥95% code coverage.**

This is **significantly higher** than the project-wide 85% threshold. This is non-negotiable because:

1. **Critical Payment Paths**: Provider adapters handle real money. A bug here means failed payments, lost revenue, or worse - incorrect charges.

2. **PayFast Sets the Bar**: The reference implementation achieved **99% coverage** (not 85%). This proves that 95%+ is achievable and should be the standard for all provider adapters.

3. **Edge Cases = Payment Failures**: High coverage catches edge cases that could cause payment failures in production:
   - Float drift in money conversion
   - Signature verification timing attacks
   - Field ordering bugs (PayFast's #1 integration bug)
   - Empty passphrase handling
   - Malformed webhook payloads

4. **Cheap to Achieve**: Coverage on provider adapters is inexpensive - mostly HTTP mocking with `respx`. There's no excuse for <95%.

5. **Regression Protection**: When you achieve 99% like PayFast, you've documented every footgun. Future maintainers won't repeat your mistakes.

**How to Check Coverage:**
```bash
# Check specific provider file coverage
pytest --cov=lekker_pay/providers/payfast.py --cov-report=term-missing

# Example output from PayFast (the standard):
# lekker_pay/providers/payfast.py    99%    (only 2 lines uncovered)
```

**If you're below 95%:** Add tests for the uncovered branches. Use `--cov-report=term-missing` to see exactly which lines need coverage.

### Required Test Categories

1. **Configuration Tests**
   - Valid configuration
   - Missing required fields
   - Frozen model (immutability)

2. **Money Conversion Tests**
   - Zero amounts
   - Small amounts (1 cent)
   - Large amounts
   - Negative amounts (should raise)
   - Float drift cases

3. **Signature/Encoding Tests**
   - Correct signature generation
   - Field ordering (if provider-specific)
   - URL encoding rules
   - Empty passphrase handling (if applicable)

4. **Create Payment Tests**
   - Successful payment creation
   - Name splitting (if required)
   - Metadata inclusion
   - HTTP mocking with respx

5. **Get Status Tests**
   - All status mappings
   - Unknown status handling

6. **Webhook Verification Tests**
   - Valid webhook
   - Signature mismatch
   - Missing signature header
   - Missing required fields
   - Malformed body
   - Unknown status
   - All status types (succeeded, failed, cancelled)
   - Empty passphrase (if applicable)
   - **Constant-time comparison test** (critical security test)

7. **Server-Side Verification Tests** (if applicable)
   - Valid verification
   - Invalid verification
   - Network errors

8. **Refund Tests**
   - Full refund success
   - Partial refund success
   - Payment not found
   - Authentication error
   - Refund error
   - Network error

9. **Signature Generation Tests** (if multiple signature types)
   - Checkout signature
   - Refund signature
   - Field ordering rules

10. **Status Mapping Tests**
    - All provider statuses
    - Unknown status raises error

11. **Amount Parsing Tests**
    - Valid amounts
    - Invalid amounts

12. **Async Context Manager Tests**
    - Client closes on exit
    - Returns self on enter

13. **Universal Footgun Regression Tests (these names are binding)**
    - `test_verify_webhook_uses_constant_time_comparison`
    - `test_money_conversion_integer_only_no_float_drift`
    - `test_verify_webhook_uses_raw_bytes_not_parsed_json`
    - `test_webhook_idempotency_same_input_same_output` — passing the same raw body to `verify_webhook` twice must produce equal `WebhookEvent` objects (the merchant-api handles dedupe via Redis but the adapter must be deterministic)
    - `test_reference_uses_merchant_supplied_not_internal_id` — verifies `WebhookEvent.reference` and `PaymentResult.reference` carry the merchant's reference, never the provider's internal numeric `id`

14. **Provider-Specific Footgun Tests** — every adapter adds at least one. PayFast's example: `test_empty_passphrase_is_not_appended`. Paystack's example: `test_paystack_api_key_used_for_both_bearer_and_webhook_hmac`.

### Test Placement Rule

Footgun tests live **inside the per-method test class where the behaviour is implemented** (e.g. the idempotency test belongs in `TestVerifyWebhook`, not in a separate dumping-ground class). You may optionally aggregate them into a `TestFootgunRegressions` class for navigability — but they must not exist only there. The behaviour-near-tests pattern means a future maintainer reading `verify_webhook` sees its full safety net beside it.

### Test Structure Example

```python
import pytest
import respx
from httpx import Response
from lekker_pay.providers.newprovider import NewProviderAdapter
from lekker_pay.base import ProviderConfig, PaymentIntent, PaymentStatus
from lekker_pay.errors import LekkerPayError, AuthenticationError, SignatureMismatchError

class TestNewProviderAdapterInit:
    """Test adapter initialization and config validation."""

    def test_init_with_valid_config(self) -> None:
        """Adapter accepts a ProviderConfig with required fields populated."""
        config = ProviderConfig(api_key="sk_test_xxx", sandbox=True)
        adapter = NewProviderAdapter(config)
        assert adapter.provider_name == "newprovider"

    def test_init_missing_required_field_raises(self) -> None:
        """Adapter raises ValueError when required field is missing."""
        config = ProviderConfig(sandbox=True)  # api_key is None
        with pytest.raises(ValueError, match="api_key"):
            NewProviderAdapter(config)

class TestVerifyWebhook:
    """Test webhook signature verification — includes footgun regressions."""

    def test_verify_webhook_uses_constant_time_comparison(self) -> None:
        """Signature comparison must use hmac.compare_digest, never ==."""
        ...

    def test_verify_webhook_uses_raw_bytes_not_parsed_json(self) -> None:
        """Signature is computed over the raw bytes — re-serialized JSON fails."""
        ...

    def test_webhook_idempotency_same_input_same_output(self) -> None:
        """Same raw body twice must produce equal WebhookEvent objects."""
        ...

    def test_reference_uses_merchant_supplied_not_internal_id(self) -> None:
        """WebhookEvent.reference is the merchant reference, not provider id."""
        ...

# ... more test classes following the per-method pattern
```

## Documentation Requirements

Create `docs/providers/newprovider.md` with:

1. **Provider Overview**
   - Official documentation links
   - Supported features
   - Limitations

2. **Authentication**
   - How to obtain credentials
   - Sandbox vs production

3. **Webhook Configuration**
   - Webhook URL format
   - Required headers
   - Signature algorithm
   - Two-step verification (if applicable)

4. **Special Considerations**
   - Provider-specific quirks
   - Rate limits
   - Idempotency handling

5. **Example Usage**
   ```python
   from lekker_pay.providers.newprovider import NewProviderAdapter
   from lekker_pay.base import ProviderConfig, PaymentIntent
   
   config = ProviderConfig(
       api_key="your_api_key",
       webhook_secret="your_webhook_secret",
       sandbox=True,
   )
   
   adapter = NewProviderAdapter(config)
   
   intent = PaymentIntent(
       amount_cents=10000,
       currency="ZAR",
       reference="ORDER-123",
       customer_email="customer@example.com",
       customer_name="John Doe",
       return_url="https://example.com/success",
       cancel_url="https://example.com/cancel",
       webhook_url="https://example.com/webhooks/payment",
   )
   
   result = await adapter.create_payment(intent)
   # Redirect customer to result.redirect_url
   ```

## Quality Gates

Before submitting a provider adapter:

- [ ] All tests pass (`pytest tests/test_newprovider.py -v`)
- [ ] Coverage ≥95% on adapter file
- [ ] `mypy --strict` passes with no errors
- [ ] `ruff check` passes with no errors
- [ ] `ruff format` applied
- [ ] Documentation complete in `docs/providers/newprovider.md`
- [ ] Adapter exported in `lekker_pay/providers/__init__.py`
- [ ] Adapter registered in router (if applicable)
- [ ] All four security footgun tests pass:
  1. Constant-time signature comparison
  2. Integer money handling
  3. Raw webhook body preservation
  4. Two-step webhook pattern (if applicable)

## Reference Implementation

The PayFast adapter ([`payfast.py`](../packages/lekker-pay/lekker_pay/providers/payfast.py)) is the **canonical reference implementation**. It demonstrates:

- ✅ **99% code coverage** (not 85% - this is the bar)
- ✅ All security patterns correctly implemented
- ✅ Comprehensive test suite (55 tests across PayFast + router)
- ✅ Two-step webhook pattern (`verify_webhook` + `validate_itn`)
- ✅ Proper error handling and mapping
- ✅ Money handling as integers (never floats)
- ✅ Constant-time signature comparison
- ✅ **Stateless config via generic `ProviderConfig`** (constructor-injected, no env reads inside the adapter)
- ✅ **Per-method test class structure** (TestCreatePayment, TestVerifyWebhook, etc.)
- ✅ **Four footgun regression tests** (constant-time, integer money, raw bytes, two-step)

### Key PayFast Patterns to Follow

1. **Stateless ProviderConfig**
   ```python
   from lekker_pay.base import ProviderConfig

   # Supply only the fields your provider needs — others stay None.
   config = ProviderConfig(
       merchant_id="10000100",
       merchant_key="46f0cd694581a",
       passphrase="",
       sandbox=True,
   )
   adapter = PayFastAdapter(config)
   ```
   No per-provider dataclass. No env reads inside the adapter — strict constructor injection.

2. **Two-Step Webhook Pattern**
   ```python
   def verify_webhook(self, headers, body) -> WebhookEvent:
       """Synchronous signature verification."""
       # Only verify signature and parse
       
   async def validate_itn(self, body: bytes) -> bool:
       """Async server-side verification (separate method)."""
       # Make HTTP call to provider
   ```

3. **Per-Method Test Classes**
   ```python
   class TestPayFastConfig: ...
   class TestMoneyConversion: ...
   class TestCheckoutSignature: ...
   class TestCreatePayment: ...
   class TestVerifyWebhook: ...
   class TestValidateITN: ...
   class TestRefund: ...
   ```

4. **Four Footgun Regression Tests**
   - `test_verify_webhook_uses_constant_time_comparison` - Security critical
   - `test_cents_to_rands_float_drift_case` - Money handling
   - `test_verify_webhook_signature_mismatch` - Raw bytes preservation
   - `test_validate_itn_success` - Two-step pattern (if applicable)

When in doubt, **copy PayFast's structure exactly**. It's battle-tested at 99% coverage.

## Common Pitfalls

1. **Using `==` for signature comparison** → Use `hmac.compare_digest()`
2. **Using floats for money** → Always use integer cents
3. **Parsing webhook body before verification** → Preserve raw bytes
4. **Making HTTP calls in `verify_webhook()`** → Use separate async method
5. **Forgetting to test constant-time comparison** → Add explicit test
6. **Not testing all status mappings** → Test every provider status
7. **Skipping async context manager tests** → Test `__aenter__`/`__aexit__`
8. **Coverage below 95%** → Add tests for uncovered branches
9. **Using provider's internal numeric `id` as `reference`** → The merchant joins on `reference` (their supplied value); the provider's `id` belongs in `raw`/`provider_payment_id` only
10. **Filtering `PaymentResult.raw` to "useful" fields** → Store the entire provider response; debugging needs the full payload
11. **Adding defensive fallbacks to alternative `ProviderConfig` fields** → Use only the fields the provider's documented API requires; silent behaviour change based on config shape is a footgun
12. **Writing helpers for trivial computations** → If `_get_base_url()` returns the same constant in both branches, it's a lie — use a module-level constant
13. **Lumping all footgun tests into `TestFootgunRegressions`** → Footgun tests live in the per-method class where the behaviour is implemented; aggregation class is optional navigation only
14. **Skipping the idempotency test** → The same webhook body twice must produce equal `WebhookEvent`s; the adapter must be deterministic even though merchant-api dedupes via Redis

## Next Steps

After implementing your adapter:

1. Run full test suite: `pytest --cov=lekker_pay --cov-report=term-missing`
2. Verify coverage: Check that `lekker_pay/providers/newprovider.py` shows ≥95%
3. Run type checker: `mypy lekker_pay/`
4. Run linter: `ruff check lekker_pay/`
5. Format code: `ruff format lekker_pay/`
6. Update `AGENTS.md` with provider-specific notes
7. Submit for review

---

**Made with Bob** 🤖