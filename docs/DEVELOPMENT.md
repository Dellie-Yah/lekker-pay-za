# Development Guide

## Quick Start

### Prerequisites

- Python 3.12 or higher
- Node.js 20+ (for pnpm)
- pnpm 8+
- Docker & Docker Compose (optional)

### Initial Setup

1. **Clone and install dependencies**
   ```bash
   # Install pnpm workspace dependencies
   pnpm install
   
   # Set up Python environment
   cd packages/lekker-pay
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   pip install -e ".[dev]"
   ```

2. **Configure environment variables**
   ```bash
   # Copy example env file
   cp .env.example .env
   
   # Edit .env with your credentials
   # PAYFAST_MERCHANT_ID=your_id
   # PAYFAST_MERCHANT_KEY=your_key
   # OZOW_API_KEY=your_key
   # YOCO_SECRET_KEY=your_key
   ```

3. **Run tests**
   ```bash
   pytest tests/ -v
   ```

## Project Structure

```
IbmBobHackathon/
├── .bob/                    # Bob Shell configuration
│   ├── settings.json        # Bob Shell settings
│   ├── mcp.json            # MCP server configuration
│   └── README.md           # Configuration docs
├── packages/
│   └── lekker-pay/         # Main Python package
│       ├── lekker_pay/     # Source code
│       ├── tests/          # Test suite
│       └── pyproject.toml  # Python project config
├── docs/                   # Documentation
│   ├── ARCHITECTURE.md     # System design
│   ├── DEVELOPMENT.md      # This file
│   └── providers/          # Provider docs
├── compose.yml             # Docker Compose config
└── pnpm-workspace.yaml     # pnpm workspace config
```

## Development Workflow

### Working with Bob Shell

Bob Shell is configured with the following MCP servers:

- **filesystem**: Access project files and documentation
- **git**: Git operations and repository management
- **github**: GitHub API integration (requires GITHUB_TOKEN)
- **python**: Python code analysis and execution
- **docker**: Docker container management
- **web-search**: Web search for documentation (requires BRAVE_API_KEY)

### Common Commands

```bash
# Run all tests
pytest tests/ -v

# Run tests with coverage
pytest tests/ --cov=lekker_pay --cov-report=html

# Run specific test file
pytest tests/test_providers.py -v

# Run tests matching pattern
pytest tests/ -k "webhook" -v

# Format code
ruff format lekker_pay/ tests/

# Lint code
ruff check lekker_pay/

# Type checking
mypy lekker_pay/

# Run all quality checks
ruff check lekker_pay/ && ruff format lekker_pay/ && mypy lekker_pay/
```

### Docker Development

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down

# Rebuild containers
docker-compose up -d --build
```

## Adding a New Payment Provider

1. **Create provider module**
   ```bash
   touch packages/lekker-pay/lekker_pay/providers/newprovider.py
   ```

2. **Implement base interface**
   ```python
   from lekker_pay.base import BasePaymentAdapter
   from typing import ClassVar
   
   class NewProviderAdapter(BasePaymentAdapter):
       provider_name: ClassVar[str] = "newprovider"
       
       async def create_payment(self, intent: PaymentIntent) -> PaymentResult:
           # Implementation
           pass
       
       def verify_webhook(self, headers: Mapping[str, str], body: bytes) -> WebhookEvent:
           # Implementation
           pass
       
       async def get_status(self, provider_payment_id: str) -> PaymentStatus:
           # Implementation
           pass
       
       async def refund(self, provider_payment_id: str, amount_cents: int | None) -> PaymentResult:
           # Implementation
           pass
   ```

3. **Add tests**
   ```bash
   touch packages/lekker-pay/tests/test_newprovider.py
   ```

4. **Document provider**
   ```bash
   touch docs/providers/newprovider.md
   ```

5. **Update exports**
   ```python
   # In lekker_pay/providers/__init__.py
   from .newprovider import NewProviderAdapter
   
   __all__ = ["NewProviderAdapter", ...]
   ```

## Testing Guidelines

### Unit Tests

- Test each provider method independently
- Mock external API calls using respx
- Test error handling
- Use parametrized tests for similar scenarios

```python
import pytest
import respx
from httpx import Response

@respx.mock
@pytest.mark.asyncio
async def test_create_payment():
    provider = NewProviderAdapter(config)
    
    respx.post("https://api.provider.com/payments").mock(
        return_value=Response(200, json={"id": "123", "status": "pending"})
    )
    
    result = await provider.create_payment(intent)
    
    assert result.provider_payment_id == "123"
    assert result.status == PaymentStatus.PENDING
```

### Integration Tests

- Test webhook handling end-to-end
- Validate signature verification
- Test with test credentials from providers

```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_webhook_integration(test_client):
    response = await test_client.post(
        "/webhooks/payfast",
        json={"payment_id": "123", "status": "complete"},
        headers={"X-Signature": "valid_signature"}
    )
    
    assert response.status_code == 200
```

### Test Fixtures

Use pytest fixtures in [`conftest.py`](../packages/lekker-pay/tests/conftest.py):

```python
import pytest
from lekker_pay.models import PaymentIntent

@pytest.fixture
def sample_intent():
    return PaymentIntent(
        amount_cents=10000,
        currency="ZAR",
        reference="ORDER-123",
        return_url="https://example.com/return",
        cancel_url="https://example.com/cancel",
        notify_url="https://example.com/webhook"
    )
```

## Debugging

### Common Issues

1. **Webhook signature validation fails**
   - Check provider credentials
   - Verify signature algorithm
   - Inspect raw payload
   - Check for encoding issues
   - Ensure using raw bytes, not parsed JSON

2. **Tests fail with connection errors**
   - Ensure respx mocks are properly configured
   - Check test fixtures in conftest.py
   - Verify `@pytest.mark.asyncio` decorator is present

3. **Import errors**
   - Ensure package is installed in editable mode: `pip install -e .`
   - Check Python path
   - Verify `__init__.py` files exist

### Debugging Tools

```bash
# Run with verbose output
pytest tests/ -vv

# Run with print statements
pytest tests/ -s

# Run with debugger
pytest tests/ --pdb

# Profile tests
pytest tests/ --profile

# Show slowest tests
pytest tests/ --durations=10
```

### Using Python Debugger

```python
import pdb

def problematic_function():
    # Set breakpoint
    pdb.set_trace()
    # Code to debug
    pass
```

## Code Quality

### Pre-commit Checks

```bash
# Format code
ruff format lekker_pay/ tests/

# Lint code
ruff check lekker_pay/ tests/

# Type check
mypy lekker_pay/

# Run all checks
ruff check lekker_pay/ && ruff format lekker_pay/ && mypy lekker_pay/
```

### Coverage Requirements

- Maintain >80% code coverage
- Test all error paths
- Test edge cases
- Mock external dependencies

```bash
# Generate coverage report
pytest tests/ --cov=lekker_pay --cov-report=html

# View report (Windows)
start htmlcov/index.html

# View report (Linux/Mac)
open htmlcov/index.html
```

## Documentation

### Docstring Format

Use Google-style docstrings:

```python
from decimal import Decimal

def process_payment(amount: Decimal, currency: str) -> PaymentResponse:
    """Process a payment transaction.
    
    Args:
        amount: Payment amount in the specified currency
        currency: ISO 4217 currency code (e.g., "ZAR")
    
    Returns:
        PaymentResponse containing transaction details
    
    Raises:
        PaymentError: If payment processing fails
        ValidationError: If input validation fails
    
    Example:
        >>> response = await process_payment(Decimal("100.00"), "ZAR")
        >>> print(response.payment_id)
        "txn_123456"
    """
    pass
```

### API Documentation

FastAPI automatically generates OpenAPI documentation:

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Performance Optimization

### Profiling

```python
import cProfile
import pstats

profiler = cProfile.Profile()
profiler.enable()

# Your code here

profiler.disable()
stats = pstats.Stats(profiler)
stats.sort_stats('cumulative')
stats.print_stats(10)
```

### Async Best Practices

- Use `async`/`await` for I/O operations
- Avoid blocking calls in async functions
- Use `asyncio.gather()` for concurrent operations
- Implement connection pooling

```python
import asyncio
import httpx

async def fetch_multiple_payments(payment_ids: list[str]):
    async with httpx.AsyncClient() as client:
        tasks = [
            client.get(f"/payments/{pid}")
            for pid in payment_ids
        ]
        responses = await asyncio.gather(*tasks)
        return responses
```

## Security Checklist

- [ ] All secrets in environment variables
- [ ] Webhook signatures validated using `hmac.compare_digest()`
- [ ] Input validation on all endpoints
- [ ] Rate limiting implemented
- [ ] HTTPS enforced in production
- [ ] Sensitive data not logged
- [ ] Dependencies regularly updated
- [ ] Security headers configured
- [ ] Money handled as integers (cents), never floats

## Deployment

### Environment Variables

Required for production:

```bash
# Payment Provider Credentials
PAYFAST_MERCHANT_ID=
PAYFAST_MERCHANT_KEY=
OZOW_API_KEY=
OZOW_SITE_CODE=
YOCO_SECRET_KEY=

# Application Settings
ENVIRONMENT=production
LOG_LEVEL=info
ALLOWED_ORIGINS=https://yourdomain.com

# Database (if applicable)
DATABASE_URL=postgresql://user:pass@host:5432/db
```

### Docker Deployment

```bash
# Build production image
docker build -t lekker-pay:latest .

# Run container
docker run -d \
  --name lekker-pay \
  -p 8000:8000 \
  --env-file .env.production \
  lekker-pay:latest
```

## Bob Shell Configuration

### MCP Servers

The project is configured with these MCP servers:

1. **Filesystem** - Access project files
2. **Git** - Version control operations
3. **GitHub** - GitHub API integration
4. **Python** - Python code analysis
5. **Docker** - Container management
6. **Web Search** - Documentation lookup

### Environment Setup

To use all MCP servers, set these environment variables:

```bash
# Required for GitHub server
export GITHUB_TOKEN="your_github_personal_access_token"

# Required for web search server
export BRAVE_API_KEY="your_brave_api_key"
```

## Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [pytest Documentation](https://docs.pytest.org/)
- [httpx Documentation](https://www.python-httpx.org/)
- [respx Documentation](https://lundberg.github.io/respx/)
- [structlog Documentation](https://www.structlog.org/)
- [Payment Provider Docs](./providers/)

## Getting Help

- Check existing documentation in `docs/`
- Review provider-specific docs in `docs/providers/`
- Use Bob Shell for code assistance
- Check GitHub issues for known problems
- Review [`AGENTS.md`](../AGENTS.md) for AI assistant guidelines
- Consult [`ARCHITECTURE.md`](./ARCHITECTURE.md) for system design

## Contributing

1. Create a feature branch
2. Make your changes
3. Write/update tests
4. Run quality checks
5. Update documentation
6. Submit pull request

### Code Review Checklist

- [ ] Tests pass with >80% coverage
- [ ] Code formatted with ruff
- [ ] Type checking passes with mypy
- [ ] Documentation updated
- [ ] Security considerations addressed
- [ ] No sensitive data in logs
- [ ] Error handling implemented
- [ ] Webhook signatures verified correctly