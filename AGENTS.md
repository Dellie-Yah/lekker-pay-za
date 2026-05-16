# Lekker Pay - AI Agent Context

## Project Overview

**Lekker Pay** is a unified Python payment adapter library for South African payment providers (PayFast, Ozow, Yoco). It provides a type-safe, secure, and provider-agnostic interface for payment processing with FastAPI integration.

## Technology Stack

- **Language**: Python 3.12+
- **Framework**: FastAPI with Pydantic v2
- **Package Manager**: pnpm (monorepo workspace)
- **Testing**: pytest with pytest-asyncio, respx for HTTP mocking
- **Type Checking**: mypy (strict mode)
- **Linting**: ruff
- **Containerization**: Docker & Docker Compose
- **HTTP Client**: httpx (async)
- **Logging**: structlog

## Project Structure

```
IbmBobHackathon/
├── .bob/                           # Bob Shell configuration
│   ├── settings.json               # Bob Shell settings
│   ├── mcp.json                    # MCP server configuration
│   └── README.md                   # Configuration documentation
├── packages/
│   └── lekker-pay/                 # Main Python package
│       ├── lekker_pay/
│       │   ├── __init__.py         # Package exports
│       │   ├── base.py             # BasePaymentAdapter (ABC)
│       │   ├── router.py           # PaymentRouter (factory/dispatcher)
│       │   ├── errors.py           # Custom exception hierarchy
│       │   └── providers/          # Provider implementations
│       │       └── __init__.py
│       ├── tests/
│       │   ├── __init__.py
│       │   └── conftest.py         # pytest fixtures
│       ├── pyproject.toml          # Python project config
│       └── README.md
├── docs/
│   ├── ARCHITECTURE.md             # System architecture & design
│   ├── DEVELOPMENT.md              # Development guide
│   ├── PROVIDER_RECIPE.md          # Step-by-step guide for new adapters
│   └── providers/                  # Provider-specific documentation
│       ├── payfast.md
│       ├── ozow.md
│       └── yoco.md
├── compose.yml                     # Docker Compose configuration
├── package.json                    # pnpm workspace root
├── pnpm-workspace.yaml             # pnpm workspace config
└── AGENTS.md                       # This file
```

## Core Architecture Principles

### 1. Provider Agnosticism
- Single interface ([`BasePaymentAdapter`](packages/lekker-pay/lekker_pay/base.py)) for all providers
- Provider-specific logic isolated in adapter classes
- Unified error handling via custom exception hierarchy

### 2. Type Safety
- Strict typing with Pydantic v2 models
- mypy strict mode enabled
- No `Any` types in public interfaces
- All models use `strict=True`

### 3. Security First
- **CRITICAL**: Always use [`hmac.compare_digest()`](https://docs.python.org/3/library/hmac.html#hmac.compare_digest) for signature verification (constant-time comparison)
- **CRITICAL**: Money as integers (`amount_cents: int`), never floats
- **CRITICAL**: Two-step webhook pattern - if provider offers server-side verification, expose it as separate async method (see [`PROVIDER_RECIPE.md`](docs/PROVIDER_RECIPE.md#step-4-implement-webhook-verification))
- Raw webhook bodies (`bytes`) for HMAC verification
- No sensitive data in logs or error messages

## Coding Standards

### Python Style

1. **Formatting**
   - Use ruff formatter (line length: 100)
   - Follow PEP 8 conventions
   - Type hints required for all function signatures

2. **Naming Conventions**
   - Classes: `PascalCase` (e.g., [`PaymentRouter`](packages/lekker-pay/lekker_pay/router.py), [`BasePaymentAdapter`](packages/lekker-pay/lekker_pay/base.py))
   - Functions/Methods: `snake_case` (e.g., `create_payment`, `verify_webhook`)
   - Constants: `UPPER_SNAKE_CASE` (e.g., `MAX_RETRY_ATTEMPTS`)
   - Private members: prefix with `_` (e.g., `_get_base_url`)

3. **Documentation**
   - Google-style docstrings for all public functions/classes
   - Include type information and exceptions in docstrings
   - Add inline comments for complex logic

4. **Error Handling**
   - Use custom exceptions from [`errors.py`](packages/lekker-pay/lekker_pay/errors.py)
   - Always validate external data (webhooks, API responses)
   - Never let raw `httpx.HTTPError` escape adapter boundary
   - Re-raise as appropriate `LekkerPayError` subclass

### FastAPI Best Practices

1. **Router Organization**
   - Group related endpoints in routers
   - Use dependency injection for shared logic
   - Implement proper request/response models with Pydantic
   - Add OpenAPI documentation tags

2. **Security**
   - Validate all webhook signatures before processing
   - Use environment variables for secrets (never hardcode)
   - Implement rate limiting for webhook endpoints
   - Sanitize all user inputs

3. **Performance**
   - Use `async`/`await` for I/O operations
   - Implement connection pooling with `httpx.AsyncClient`
   - Cache provider configurations
   - Use background tasks for non-blocking operations

## Critical Security Rules

### 1. Webhook Signature Verification

**ALWAYS use constant-time comparison to prevent timing attacks:**

```python
import hmac

# ✅ CORRECT
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

## Provider Adapter Pattern

All provider adapters must implement [`BasePaymentAdapter`](packages/lekker-pay/lekker_pay/base.py):

```python
class BasePaymentAdapter(ABC):
    provider_name: ClassVar[str]
    
    @abstractmethod
    async def create_payment(self, intent: PaymentIntent) -> PaymentResult:
        """Create a payment with the provider."""
        
    @abstractmethod
    async def get_status(self, provider_payment_id: str) -> PaymentStatus:
        """Get payment status from provider."""
        
    @abstractmethod
    def verify_webhook(self, headers: Mapping[str, str], body: bytes) -> WebhookEvent:
        """Verify and parse webhook (sync for simplicity)."""
        
    @abstractmethod
    async def refund(self, provider_payment_id: str, amount_cents: int | None) -> PaymentResult:
        """Refund a payment (full or partial)."""
```

### Key Design Decisions

- **Stateless**: Configuration injected via constructor
- **Async by default**: All I/O operations are async
- **Sync webhook verification**: Cryptographic operations don't need async
- **Money as integers**: `amount_cents` is always `int`, never `float`

## Testing Requirements

### Unit Tests (with respx)

```python
import respx
from httpx import Response

@respx.mock
async def test_create_payment(sample_intent):
    respx.post("https://sandbox.provider.com/payments").mock(
        return_value=Response(200, json={"id": "123", "status": "pending"})
    )
    
    adapter = ProviderAdapter(config)
    result = await adapter.create_payment(sample_intent)
    
    assert result.provider_payment_id == "123"
    assert result.status == PaymentStatus.PENDING
```

### Coverage Requirements

- **Project-wide**: Maintain ≥85% code coverage
- **Provider adapters**: MUST achieve ≥95% coverage (see [`PROVIDER_RECIPE.md`](docs/PROVIDER_RECIPE.md#testing-requirements))
  - PayFast reference implementation: 99% coverage
  - High coverage is critical for payment paths
  - Use: `pytest --cov=lekker_pay/providers/payfast.py --cov-report=term-missing`
- Test all error paths
- Test edge cases
- Mock external dependencies with respx
- Use parametrized tests for similar scenarios

### Test Organization

- Use pytest fixtures in [`conftest.py`](packages/lekker-pay/tests/conftest.py)
- Group tests by provider
- Mark integration tests with `@pytest.mark.integration`

## Common Development Tasks

### Running Tests

```bash
cd packages/lekker-pay
pytest tests/ -v                    # Run all tests
pytest tests/ --cov=lekker_pay      # With coverage
pytest tests/ -k "webhook"          # Run specific tests
```

### Code Quality

```bash
ruff check lekker_pay/              # Lint code
ruff format lekker_pay/             # Format code
mypy lekker_pay/                    # Type check
```

### Docker Development

```bash
docker-compose up -d                # Start services
docker-compose logs -f              # View logs
docker-compose down                 # Stop services
```

## Adding a New Payment Provider

**IMPORTANT**: Follow the step-by-step guide in [`PROVIDER_RECIPE.md`](docs/PROVIDER_RECIPE.md) for implementing new provider adapters.

Quick checklist:
1. **Create provider module**: `lekker_pay/providers/newprovider.py`
2. **Implement [`BasePaymentAdapter`](packages/lekker-pay/lekker_pay/base.py)** interface
3. **Add comprehensive tests**: `tests/providers/test_newprovider.py` (≥95% coverage)
4. **Document provider**: `docs/providers/newprovider.md`
5. **Update exports**: Add to `lekker_pay/providers/__init__.py`
6. **Register in router**: `router.register_adapter("newprovider", NewProviderAdapter)`

See [`docs/PROVIDER_RECIPE.md`](docs/PROVIDER_RECIPE.md) for detailed implementation guide and [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for architecture information.

## Provider-Specific Considerations

### PayFast
- Uses MD5 signature validation
- Requires merchant credentials (merchant_id, merchant_key)
- Supports ITN (Instant Transaction Notification)
- Docs: https://developers.payfast.co.za/

### Ozow
- Uses HMAC-SHA256 for webhook validation
- Requires API key and site code
- Supports real-time payment notifications
- Docs: https://docs.ozow.com/

### Yoco
- OAuth 2.0 authentication
- Webhook signature verification with secret key
- Supports card payments and mobile money
- Docs: https://developer.yoco.com/

## Debugging Guidelines

### Common Issues

1. **Webhook signature validation fails**
   - Verify you're using raw bytes, not parsed JSON
   - Check signature algorithm matches provider docs
   - Inspect raw payload and headers
   - Verify credentials are correct

2. **Tests fail with connection errors**
   - Ensure respx mocks are properly configured
   - Check test fixtures in [`conftest.py`](packages/lekker-pay/tests/conftest.py)
   - Verify `@pytest.mark.asyncio` decorator is present

3. **Import errors**
   - Ensure package installed in editable mode: `pip install -e .`
   - Check `__init__.py` files exist in all packages
   - Verify Python path includes project root

### Debugging Tools

```bash
pytest tests/ -vv                   # Verbose output
pytest tests/ -s                    # Show print statements
pytest tests/ --pdb                 # Drop into debugger on failure
pytest tests/ --durations=10        # Show slowest tests
```

## Observability

### Structured Logging

```python
import structlog

logger = structlog.get_logger()

logger.info(
    "payment_created",
    provider="payfast",
    reference="ORDER-123",
    amount_cents=10000,
    correlation_id=correlation_id
)
```

### What to Log

- Payment creation/completion events
- Webhook verification results
- Provider API errors
- Performance metrics (latency)

### What NOT to Log

- Card numbers or CVV
- API keys or secrets
- Full webhook payloads (may contain PII)
- Customer personal information

## Compliance & Standards

- **PCI DSS**: Library never handles card data directly
- **POPIA**: No PII stored in library (merchant-api responsibility)
- **Idempotency**: Enforced at merchant-api layer via Redis
- **Webhook replay protection**: 24hr TTL in Redis

## AI Assistant Guidelines

When working on this project:

1. **ALWAYS** verify webhook signatures using [`hmac.compare_digest()`](https://docs.python.org/3/library/hmac.html#hmac.compare_digest)
2. **ALWAYS** use integers for money amounts, never floats
3. **ALWAYS** preserve raw bytes for webhook body verification
4. **ALWAYS** check existing provider implementations before creating new ones
5. **ALWAYS** follow the established patterns in [`base.py`](packages/lekker-pay/lekker_pay/base.py)
6. **ALWAYS** write comprehensive tests with >80% coverage
7. **ALWAYS** use type hints and Pydantic models for data validation
8. **ALWAYS** handle errors gracefully and re-raise as `LekkerPayError` subclasses
9. **ALWAYS** document public APIs with Google-style docstrings
10. **NEVER** log sensitive data (API keys, card numbers, PII)

## Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [pytest Documentation](https://docs.pytest.org/)
- [httpx Documentation](https://www.python-httpx.org/)
- [structlog Documentation](https://www.structlog.org/)
- [Architecture Documentation](docs/ARCHITECTURE.md)
- [Development Guide](docs/DEVELOPMENT.md)