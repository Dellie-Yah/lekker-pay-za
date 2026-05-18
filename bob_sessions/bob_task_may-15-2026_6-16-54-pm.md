**User:**

<task>
Explain in great detail what you have done.
</task>
<environment_details>
# VSCode Visible Files
compose.yml

# VSCode Open Tabs
package.json,pnpm-workspace.yaml,packages/lekker-pay/pyproject.toml,packages/lekker-pay/README.md,packages/lekker-pay/lekker_pay/errors.py,packages/lekker-pay/lekker_pay/base.py,packages/lekker-pay/lekker_pay/router.py,packages/lekker-pay/lekker_pay/__init__.py,packages/lekker-pay/lekker_pay/providers/__init__.py,packages/lekker-pay/tests/__init__.py,packages/lekker-pay/tests/conftest.py,docs/ARCHITECTURE.md,docs/providers/payfast.md,docs/providers/ozow.md,docs/providers/yoco.md,compose.yml

# Current Time
Current time in ISO 8601 UTC format: 2026-05-15T16:15:13.376Z
User time zone: Africa/Johannesburg, UTC+2:00

# Current Cost
$0.00

# Review Exclusions
The following file patterns are excluded from code reviews:
- .vscode/**
- .env
- secrets/

# Current Mode
<slug>code</slug>
<name>💻 Code</name>


# Current Workspace Directory (d:/DELRON/CODING PROJECTS/IbmBobHackathon) Files
.gitignore
compose.yml
LICENSE
package.json
pnpm-workspace.yaml
README.md
.bob/
docs/
docs/ARCHITECTURE.md
docs/providers/
docs/providers/ozow.md
docs/providers/payfast.md
docs/providers/yoco.md
packages/
packages/lekker-pay/
packages/lekker-pay/pyproject.toml
packages/lekker-pay/README.md
packages/lekker-pay/lekker_pay/
packages/lekker-pay/lekker_pay/__init__.py
packages/lekker-pay/lekker_pay/base.py
packages/lekker-pay/lekker_pay/errors.py
packages/lekker-pay/lekker_pay/router.py
packages/lekker-pay/lekker_pay/providers/
packages/lekker-pay/lekker_pay/providers/__init__.py
packages/lekker-pay/tests/
packages/lekker-pay/tests/__init__.py
packages/lekker-pay/tests/conftest.py
You have not created a todo list yet. Create one with `update_todo_list` if your task is complicated or involves multiple steps.
</environment_details>

---

**Assistant:**

I'll analyze the project structure and provide a detailed explanation of what has been done. Let me start by examining the key files.

<read_file>
<args>
<file>
<path>README.md</path>
</file>
<file>
<path>docs/ARCHITECTURE.md</path>
</file>
<file>
<path>packages/lekker-pay/README.md</path>
</file>
<file>
<path>packages/lekker-pay/pyproject.toml</path>
</file>
<file>
<path>package.json</path>
</file>
</args>
</read_file>

---

**User:**

[read_file for 5 files] Result:
<files>
<file><path>README.md</path>
<content lines="1-2">
1 | # lekker-pay-za
2 | IBM BOB HACKATHON IDEA!😁
</content>
</file>
<file><path>docs/ARCHITECTURE.md</path>
<content lines="1-314">
  1 | # Lekker Pay Architecture
  2 | 
  3 | ## Overview
  4 | 
  5 | Lekker Pay is a unified payment adapter library that provides a single interface for integrating with multiple South African payment providers. The architecture is designed around three core principles:
  6 | 
  7 | 1. **Provider Agnosticism** - One interface, multiple providers
  8 | 2. **Type Safety** - Strict typing with Pydantic v2 and mypy
  9 | 3. **Security First** - Constant-time signature verification, no float money
 10 | 
 11 | ## System Architecture
 12 | 
 13 | ```mermaid
 14 | graph TB
 15 |     subgraph "Merchant Application"
 16 |         MA[Merchant API<br/>FastAPI]
 17 |         MW[Merchant Web<br/>Next.js]
 18 |     end
 19 |     
 20 |     subgraph "Lekker Pay Library"
 21 |         PR[PaymentRouter]
 22 |         BA[BasePaymentAdapter]
 23 |         PF[PayFastAdapter]
 24 |         OZ[OzowAdapter]
 25 |         YO[YocoAdapter]
 26 |     end
 27 |     
 28 |     subgraph "Payment Providers"
 29 |         PFS[PayFast API]
 30 |         OZS[Ozow API]
 31 |         YOS[Yoco API]
 32 |     end
 33 |     
 34 |     MW -->|HTTP| MA
 35 |     MA -->|create_payment| PR
 36 |     PR -->|dispatch| BA
 37 |     BA -.implements.- PF
 38 |     BA -.implements.- OZ
 39 |     BA -.implements.- YO
 40 |     
 41 |     PF -->|HTTPS| PFS
 42 |     OZ -->|HTTPS| OZS
 43 |     YO -->|HTTPS| YOS
 44 |     
 45 |     PFS -.webhook.-> MA
 46 |     OZS -.webhook.-> MA
 47 |     YOS -.webhook.-> MA
 48 |     
 49 |     MA -->|verify_webhook| PR
 50 | ```
 51 | 
 52 | ## Core Components
 53 | 
 54 | ### 1. BasePaymentAdapter (Abstract Base Class)
 55 | 
 56 | The contract that all provider adapters must implement:
 57 | 
 58 | ```python
 59 | class BasePaymentAdapter(ABC):
 60 |     provider_name: ClassVar[str]
 61 |     
 62 |     async def create_payment(self, intent: PaymentIntent) -> PaymentResult
 63 |     async def get_status(self, provider_payment_id: str) -> PaymentStatus
 64 |     def verify_webhook(self, headers: Mapping[str,str], body: bytes) -> WebhookEvent
 65 |     async def refund(self, provider_payment_id: str, amount_cents: int | None) -> PaymentResult
 66 | ```
 67 | 
 68 | **Key Design Decisions:**
 69 | 
 70 | - **Stateless**: Config injected via constructor, no environment reads
 71 | - **Async by default**: All I/O operations are async (except webhook verification)
 72 | - **Sync webhook verification**: Cryptographic operations don't need async, keeps testing simple
 73 | - **Money as integers**: `amount_cents` is always `int`, never `float`
 74 | 
 75 | ### 2. PaymentRouter (Factory & Dispatcher)
 76 | 
 77 | Manages provider registration and dispatches requests to the appropriate adapter:
 78 | 
 79 | ```python
 80 | router = PaymentRouter(provider_configs)
 81 | router.register_adapter("payfast", PayFastAdapter)
 82 | result = await router.create_payment("payfast", intent)
 83 | ```
 84 | 
 85 | **Responsibilities:**
 86 | - Lazy adapter instantiation (created on first use)
 87 | - Provider validation (registered + configured)
 88 | - Unified error handling
 89 | 
 90 | ### 3. Pydantic Models
 91 | 
 92 | All data structures use Pydantic v2 with strict mode:
 93 | 
 94 | - **PaymentIntent**: Provider-agnostic payment request
 95 | - **PaymentResult**: Unified payment response
 96 | - **WebhookEvent**: Verified webhook payload
 97 | - **ProviderConfig**: Provider credentials and settings
 98 | 
 99 | **Type Safety Rules:**
100 | - No `Any` types in public interfaces
101 | - All models use `strict=True`
102 | - `HttpUrl` for URLs, `EmailStr` for emails
103 | - Enums for status values
104 | 
105 | ### 4. Error Hierarchy
106 | 
107 | ```
108 | LekkerPayError (base)
109 | └── ProviderError
110 |     ├── AuthenticationError
111 |     ├── InvalidRequestError
112 |     ├── NetworkError
113 |     ├── SignatureMismatchError
114 |     ├── RateLimitError
115 |     ├── PaymentNotFoundError
116 |     └── RefundError
117 | ```
118 | 
119 | **Error Handling Contract:**
120 | - Adapters catch all provider-specific exceptions
121 | - Re-raise as appropriate `LekkerPayError` subclass
122 | - Never let raw `httpx.HTTPError` escape adapter boundary
123 | 
124 | ## Provider Adapter Pattern
125 | 
126 | Each provider adapter follows this structure:
127 | 
128 | ```python
129 | class ProviderAdapter(BasePaymentAdapter):
130 |     provider_name = "provider"
131 |     
132 |     def __init__(self, config: ProviderConfig) -> None:
133 |         self.config = config
134 |         self.client = httpx.AsyncClient(
135 |             base_url=self._get_base_url(),
136 |             timeout=30.0
137 |         )
138 |     
139 |     def _get_base_url(self) -> str:
140 |         """Return sandbox or production URL based on config."""
141 |         if self.config.sandbox:
142 |             return "https://sandbox.provider.com"
143 |         return "https://api.provider.com"
144 |     
145 |     async def create_payment(self, intent: PaymentIntent) -> PaymentResult:
146 |         try:
147 |             # 1. Build provider-specific request
148 |             # 2. Sign/authenticate request
149 |             # 3. Make HTTP call
150 |             # 4. Parse response
151 |             # 5. Map to PaymentResult
152 |             pass
153 |         except httpx.HTTPError as e:
154 |             raise NetworkError(str(e), provider=self.provider_name)
155 |     
156 |     def verify_webhook(self, headers: Mapping[str,str], body: bytes) -> WebhookEvent:
157 |         # 1. Extract signature from headers/body
158 |         # 2. Compute expected signature
159 |         # 3. Compare using hmac.compare_digest (NEVER ==)
160 |         # 4. Parse and return WebhookEvent
161 |         pass
162 | ```
163 | 
164 | ## Security Considerations
165 | 
166 | ### 1. Webhook Signature Verification
167 | 
168 | **CRITICAL**: Always use constant-time comparison:
169 | 
170 | ```python
171 | import hmac
172 | 
173 | # ✅ CORRECT
174 | if not hmac.compare_digest(expected_sig, received_sig):
175 |     raise SignatureMismatchError("Invalid signature")
176 | 
177 | # ❌ WRONG - timing attack vulnerability
178 | if expected_sig != received_sig:
179 |     raise SignatureMismatchError("Invalid signature")
180 | ```
181 | 
182 | ### 2. Money Handling
183 | 
184 | **CRITICAL**: Never use floats for money:
185 | 
186 | ```python
187 | # ✅ CORRECT
188 | amount_cents = 10000  # R100.00
189 | 
190 | # ❌ WRONG
191 | amount_rands = 100.00  # floating point precision issues
192 | ```
193 | 
194 | ### 3. Raw Webhook Bodies
195 | 
196 | For HMAC verification, the body must be raw bytes:
197 | 
198 | ```python
199 | # ✅ CORRECT
200 | @app.post("/webhooks/payment")
201 | async def webhook(request: Request):
202 |     body = await request.body()  # Raw bytes
203 |     event = adapter.verify_webhook(request.headers, body)
204 | 
205 | # ❌ WRONG
206 | @app.post("/webhooks/payment")
207 | async def webhook(payload: dict):
208 |     # Body already parsed - signature verification will fail
209 | ```
210 | 
211 | ## Testing Strategy
212 | 
213 | ### Unit Tests (respx mocks)
214 | 
215 | ```python
216 | import respx
217 | from httpx import Response
218 | 
219 | @respx.mock
220 | async def test_create_payment(sample_intent):
221 |     respx.post("https://sandbox.provider.com/payments").mock(
222 |         return_value=Response(200, json={"id": "123", "status": "pending"})
223 |     )
224 |     
225 |     adapter = ProviderAdapter(config)
226 |     result = await adapter.create_payment(sample_intent)
227 |     
228 |     assert result.provider_payment_id == "123"
229 |     assert result.status == PaymentStatus.PENDING
230 | ```
231 | 
232 | ### Integration Tests (optional, env-gated)
233 | 
234 | ```python
235 | @pytest.mark.skipif(not os.getenv("RUN_INTEGRATION_TESTS"), reason="Integration tests disabled")
236 | async def test_create_payment_live():
237 |     # Use real sandbox API
238 |     pass
239 | ```
240 | 
241 | ## Deployment Architecture
242 | 
243 | ### Development
244 | ```
245 | docker-compose up
246 | ├── postgres:16
247 | ├── redis:7
248 | └── merchant-api (FastAPI)
249 | ```
250 | 
251 | ### Production (conceptual)
252 | ```
253 | Vercel (merchant-web)
254 |     ↓
255 | Railway/Render (merchant-api)
256 |     ↓
257 | Managed Postgres + Redis
258 | ```
259 | 
260 | ## Extension Points
261 | 
262 | ### Adding a New Provider
263 | 
264 | 1. Create `lekker_pay/providers/newprovider.py`
265 | 2. Implement `BasePaymentAdapter`
266 | 3. Add tests in `tests/providers/test_newprovider.py`
267 | 4. Register in router: `router.register_adapter("newprovider", NewProviderAdapter)`
268 | 5. Document in `docs/providers/newprovider.md`
269 | 
270 | See `docs/PROVIDER_RECIPE.md` for detailed instructions.
271 | 
272 | ## Performance Considerations
273 | 
274 | - **Connection pooling**: httpx.AsyncClient reuses connections
275 | - **Timeouts**: 30s default, configurable per provider
276 | - **Retries**: Not implemented in v1 (merchant-api layer responsibility)
277 | - **Rate limiting**: Providers may rate limit; adapters raise `RateLimitError`
278 | 
279 | ## Observability
280 | 
281 | ### Structured Logging (structlog)
282 | 
283 | ```python
284 | import structlog
285 | 
286 | logger = structlog.get_logger()
287 | 
288 | logger.info(
289 |     "payment_created",
290 |     provider="payfast",
291 |     reference="ORDER-123",
292 |     amount_cents=10000,
293 |     correlation_id=correlation_id
294 | )
295 | ```
296 | 
297 | ### Metrics (future)
298 | 
299 | - Payment creation latency by provider
300 | - Webhook verification success/failure rate
301 | - Provider error rates
302 | 
303 | ## Compliance & Standards
304 | 
305 | - **PCI DSS**: Library never handles card data directly
306 | - **POPIA**: No PII stored in library (merchant-api responsibility)
307 | - **Idempotency**: Enforced at merchant-api layer via Redis
308 | - **Webhook replay protection**: 24hr TTL in Redis
309 | 
310 | ## References
311 | 
312 | - [PayFast API Docs](https://developers.payfast.co.za/)
313 | - [Ozow API Docs](https://docs.ozow.com/)
314 | - [Yoco API Docs](https://developer.yoco.com/)
</content>
</file>
<file><path>packages/lekker-pay/README.md</path>
<content lines="1-53">
 1 | # Lekker Pay
 2 | 
 3 | Unified payment adapter library for South African payment providers.
 4 | 
 5 | ## Supported Providers
 6 | 
 7 | - PayFast
 8 | - Ozow
 9 | - Yoco
10 | 
11 | ## Installation
12 | 
13 | ```bash
14 | pip install lekker-pay
15 | ```
16 | 
17 | ## Quick Start
18 | 
19 | ```python
20 | from lekker_pay import PaymentRouter, PaymentIntent, ProviderConfig
21 | 
22 | # Configure providers
23 | config = {
24 |     "payfast": ProviderConfig(
25 |         merchant_id="10000100",
26 |         merchant_key="46f0cd694581a",
27 |         passphrase="jt7NOE43FZPn",
28 |         sandbox=True
29 |     )
30 | }
31 | 
32 | # Initialize router
33 | router = PaymentRouter(config)
34 | 
35 | # Create payment
36 | intent = PaymentIntent(
37 |     amount_cents=10000,  # R100.00
38 |     currency="ZAR",
39 |     reference="ORDER-123",
40 |     customer_email="customer@example.com",
41 |     customer_name="John Doe",
42 |     return_url="https://example.com/success",
43 |     cancel_url="https://example.com/cancel",
44 |     webhook_url="https://example.com/webhooks/payment"
45 | )
46 | 
47 | result = await router.create_payment("payfast", intent)
48 | # Redirect customer to result.redirect_url
49 | ```
50 | 
51 | ## Documentation
52 | 
53 | See [docs/](../../docs/) for full documentation.
</content>
</file>
<file><path>packages/lekker-pay/pyproject.toml</path>
<content lines="1-116">
  1 | [project]
  2 | name = "lekker-pay"
  3 | version = "0.1.0"
  4 | description = "Unified payment adapter library for South African payment providers"
  5 | readme = "README.md"
  6 | requires-python = ">=3.12"
  7 | license = { text = "MIT" }
  8 | authors = [
  9 |     { name = "Lekker Pay Team" }
 10 | ]
 11 | keywords = ["payments", "south-africa", "payfast", "ozow", "yoco", "payment-gateway"]
 12 | classifiers = [
 13 |     "Development Status :: 3 - Alpha",
 14 |     "Intended Audience :: Developers",
 15 |     "License :: OSI Approved :: MIT License",
 16 |     "Programming Language :: Python :: 3.12",
 17 |     "Topic :: Software Development :: Libraries :: Python Modules",
 18 | ]
 19 | 
 20 | dependencies = [
 21 |     "pydantic>=2.0.0,<3.0.0",
 22 |     "pydantic[email]>=2.0.0,<3.0.0",
 23 |     "httpx>=0.27.0,<1.0.0",
 24 |     "cryptography>=42.0.0,<43.0.0",
 25 |     "structlog>=24.0.0,<25.0.0",
 26 | ]
 27 | 
 28 | [project.optional-dependencies]
 29 | dev = [
 30 |     "pytest>=8.0.0,<9.0.0",
 31 |     "pytest-asyncio>=0.23.0,<1.0.0",
 32 |     "pytest-cov>=4.1.0,<5.0.0",
 33 |     "respx>=0.21.0,<1.0.0",
 34 |     "ruff>=0.3.0,<1.0.0",
 35 |     "mypy>=1.9.0,<2.0.0",
 36 | ]
 37 | 
 38 | [build-system]
 39 | requires = ["hatchling"]
 40 | build-backend = "hatchling.build"
 41 | 
 42 | [tool.hatch.build.targets.wheel]
 43 | packages = ["lekker_pay"]
 44 | 
 45 | [tool.pytest.ini_options]
 46 | testpaths = ["tests"]
 47 | asyncio_mode = "auto"
 48 | addopts = [
 49 |     "--strict-markers",
 50 |     "--strict-config",
 51 |     "--cov=lekker_pay",
 52 |     "--cov-report=term-missing:skip-covered",
 53 |     "--cov-report=html",
 54 |     "--cov-report=xml",
 55 | ]
 56 | 
 57 | [tool.coverage.run]
 58 | source = ["lekker_pay"]
 59 | branch = true
 60 | 
 61 | [tool.coverage.report]
 62 | exclude_lines = [
 63 |     "pragma: no cover",
 64 |     "def __repr__",
 65 |     "raise AssertionError",
 66 |     "raise NotImplementedError",
 67 |     "if __name__ == .__main__.:",
 68 |     "if TYPE_CHECKING:",
 69 |     "@abstractmethod",
 70 | ]
 71 | 
 72 | [tool.mypy]
 73 | python_version = "3.12"
 74 | strict = true
 75 | warn_return_any = true
 76 | warn_unused_configs = true
 77 | disallow_untyped_defs = true
 78 | disallow_any_generics = true
 79 | disallow_subclassing_any = true
 80 | disallow_untyped_calls = true
 81 | disallow_incomplete_defs = true
 82 | check_untyped_defs = true
 83 | disallow_untyped_decorators = true
 84 | no_implicit_optional = true
 85 | warn_redundant_casts = true
 86 | warn_unused_ignores = true
 87 | warn_no_return = true
 88 | warn_unreachable = true
 89 | strict_equality = true
 90 | 
 91 | [tool.ruff]
 92 | target-version = "py312"
 93 | line-length = 100
 94 | select = [
 95 |     "E",   # pycodestyle errors
 96 |     "W",   # pycodestyle warnings
 97 |     "F",   # pyflakes
 98 |     "I",   # isort
 99 |     "B",   # flake8-bugbear
100 |     "C4",  # flake8-comprehensions
101 |     "UP",  # pyupgrade
102 |     "ARG", # flake8-unused-arguments
103 |     "SIM", # flake8-simplify
104 | ]
105 | ignore = [
106 |     "E501",  # line too long (handled by formatter)
107 | ]
108 | 
109 | [tool.ruff.lint.per-file-ignores]
110 | "tests/**/*.py" = [
111 |     "ARG",  # Unused function args in tests (fixtures)
112 |     "S101", # Use of assert in tests
113 | ]
114 | 
115 | [tool.ruff.lint.isort]
116 | known-first-party = ["lekker_pay"]
</content>
</file>
<file><path>package.json</path>
<content lines="1-22">
 1 | {
 2 |   "name": "lekker-pay-monorepo",
 3 |   "version": "0.1.0",
 4 |   "private": true,
 5 |   "description": "Unified payment adapter library for South African payment providers",
 6 |   "scripts": {
 7 |     "dev:web": "pnpm --filter merchant-web dev",
 8 |     "dev:api": "pnpm --filter merchant-api dev",
 9 |     "build": "pnpm -r build",
10 |     "test": "pnpm -r test",
11 |     "lint": "pnpm -r lint",
12 |     "format": "pnpm -r format"
13 |   },
14 |   "keywords": ["payments", "south-africa", "payfast", "ozow", "yoco"],
15 |   "author": "",
16 |   "license": "MIT",
17 |   "packageManager": "pnpm@8.15.0",
18 |   "engines": {
19 |     "node": ">=20.0.0",
20 |     "pnpm": ">=8.0.0"
21 |   }
22 | }
</content>
</file>
</files>
<environment_details>
# VSCode Visible Files
compose.yml

# VSCode Open Tabs
package.json,pnpm-workspace.yaml,packages/lekker-pay/pyproject.toml,packages/lekker-pay/README.md,packages/lekker-pay/lekker_pay/errors.py,packages/lekker-pay/lekker_pay/base.py,packages/lekker-pay/lekker_pay/router.py,packages/lekker-pay/lekker_pay/__init__.py,packages/lekker-pay/lekker_pay/providers/__init__.py,packages/lekker-pay/tests/__init__.py,packages/lekker-pay/tests/conftest.py,docs/ARCHITECTURE.md,docs/providers/payfast.md,docs/providers/ozow.md,docs/providers/yoco.md,compose.yml

# Current Time
Current time in ISO 8601 UTC format: 2026-05-15T16:15:33.388Z
User time zone: Africa/Johannesburg, UTC+2:00

# Current Cost
$0.01

# Review Exclusions
The following file patterns are excluded from code reviews:
- .vscode/**
- .env
- secrets/

# Current Mode
<slug>code</slug>
<name>💻 Code</name>
You have not created a todo list yet. Create one with `update_todo_list` if your task is complicated or involves multiple steps.
</environment_details>

---

**Assistant:**

<read_file>
<args>
<file>
<path>packages/lekker-pay/lekker_pay/__init__.py</path>
</file>
<file>
<path>packages/lekker-pay/lekker_pay/base.py</path>
</file>
<file>
<path>packages/lekker-pay/lekker_pay/router.py</path>
</file>
<file>
<path>packages/lekker-pay/lekker_pay/errors.py</path>
</file>
<file>
<path>compose.yml</path>
</file>
</args>
</read_file>

---

**User:**

[read_file for 5 files] Result:
<files>
<file><path>packages/lekker-pay/lekker_pay/__init__.py</path>
<content lines="1-82">
 1 | """
 2 | Lekker Pay - Unified payment adapter library for South African payment providers.
 3 | 
 4 | This package provides a single interface for integrating with multiple SA payment
 5 | providers (PayFast, Ozow, Yoco) through a consistent API.
 6 | 
 7 | Example:
 8 |     from lekker_pay import PaymentRouter, PaymentIntent, ProviderConfig
 9 |     
10 |     config = {
11 |         "payfast": ProviderConfig(
12 |             merchant_id="10000100",
13 |             merchant_key="46f0cd694581a",
14 |             passphrase="jt7NOE43FZPn",
15 |             sandbox=True
16 |         )
17 |     }
18 |     
19 |     router = PaymentRouter(config)
20 |     
21 |     intent = PaymentIntent(
22 |         amount_cents=10000,
23 |         currency="ZAR",
24 |         reference="ORDER-123",
25 |         customer_email="customer@example.com",
26 |         customer_name="John Doe",
27 |         return_url="https://example.com/success",
28 |         cancel_url="https://example.com/cancel",
29 |         webhook_url="https://example.com/webhooks/payment"
30 |     )
31 |     
32 |     result = await router.create_payment("payfast", intent)
33 | """
34 | 
35 | __version__ = "0.1.0"
36 | 
37 | from lekker_pay.base import (
38 |     BasePaymentAdapter,
39 |     PaymentIntent,
40 |     PaymentResult,
41 |     PaymentStatus,
42 |     ProviderConfig,
43 |     WebhookEvent,
44 | )
45 | from lekker_pay.errors import (
46 |     AuthenticationError,
47 |     InvalidRequestError,
48 |     LekkerPayError,
49 |     NetworkError,
50 |     PaymentNotFoundError,
51 |     ProviderError,
52 |     RateLimitError,
53 |     RefundError,
54 |     SignatureMismatchError,
55 | )
56 | from lekker_pay.router import PaymentRouter
57 | 
58 | __all__ = [
59 |     # Version
60 |     "__version__",
61 |     # Core classes
62 |     "PaymentRouter",
63 |     "BasePaymentAdapter",
64 |     # Models
65 |     "PaymentIntent",
66 |     "PaymentResult",
67 |     "PaymentStatus",
68 |     "ProviderConfig",
69 |     "WebhookEvent",
70 |     # Exceptions
71 |     "LekkerPayError",
72 |     "ProviderError",
73 |     "AuthenticationError",
74 |     "InvalidRequestError",
75 |     "NetworkError",
76 |     "SignatureMismatchError",
77 |     "RateLimitError",
78 |     "PaymentNotFoundError",
79 |     "RefundError",
80 | ]
81 | 
82 | # Made with Bob
</content>
</file>
<file><path>packages/lekker-pay/lekker_pay/base.py</path>
<content lines="1-307">
  1 | """
  2 | Base interface contract for all payment adapters.
  3 | 
  4 | This module defines the abstract base class and Pydantic models that all
  5 | provider adapters must implement. The interface is designed to be:
  6 | - Provider-agnostic
  7 | - Type-safe (mypy --strict compliant)
  8 | - Money-safe (always integers, never floats)
  9 | - Security-conscious (constant-time signature comparison)
 10 | """
 11 | 
 12 | from abc import ABC, abstractmethod
 13 | from datetime import datetime
 14 | from enum import Enum
 15 | from typing import ClassVar, Literal, Mapping
 16 | 
 17 | from pydantic import BaseModel, EmailStr, Field, HttpUrl
 18 | 
 19 | 
 20 | class PaymentStatus(str, Enum):
 21 |     """
 22 |     Unified payment status across all providers.
 23 |     
 24 |     Adapters must map provider-specific statuses to these values.
 25 |     """
 26 | 
 27 |     PENDING = "pending"  # Payment initiated but not yet processing
 28 |     PROCESSING = "processing"  # Payment actively being processed by provider
 29 |     SUCCEEDED = "succeeded"  # Payment completed successfully
 30 |     FAILED = "failed"  # Payment failed (insufficient funds, declined, etc.)
 31 |     REFUNDED = "refunded"  # Payment was refunded (full or partial)
 32 |     CANCELLED = "cancelled"  # Payment was cancelled before completion
 33 | 
 34 | 
 35 | class ProviderConfig(BaseModel):
 36 |     """
 37 |     Generic provider configuration.
 38 |     
 39 |     Each provider uses only the fields it needs. Adapters are stateless
 40 |     and receive config via constructor - no environment variable reads
 41 |     inside adapter classes.
 42 |     
 43 |     Example:
 44 |         PayFast uses: merchant_id, merchant_key, passphrase, sandbox
 45 |         Yoco uses: api_key, webhook_secret, sandbox
 46 |         Ozow uses: api_key, site_code, private_key, sandbox
 47 |     """
 48 | 
 49 |     api_key: str | None = None
 50 |     api_secret: str | None = None
 51 |     merchant_id: str | None = None
 52 |     merchant_key: str | None = None
 53 |     site_code: str | None = None
 54 |     private_key: str | None = None
 55 |     passphrase: str | None = None
 56 |     webhook_secret: str | None = None
 57 |     sandbox: bool = True
 58 |     base_url: str | None = None  # Override for testing
 59 | 
 60 | 
 61 | class PaymentIntent(BaseModel):
 62 |     """
 63 |     Provider-agnostic payment request.
 64 |     
 65 |     CRITICAL: amount_cents is always an integer. Never use floats for money.
 66 |     To represent R100.00, use amount_cents=10000.
 67 |     
 68 |     Example:
 69 |         intent = PaymentIntent(
 70 |             amount_cents=10000,  # R100.00
 71 |             currency="ZAR",
 72 |             reference="ORDER-123",
 73 |             customer_email="customer@example.com",
 74 |             customer_name="John Doe",
 75 |             return_url="https://example.com/success",
 76 |             cancel_url="https://example.com/cancel",
 77 |             webhook_url="https://example.com/webhooks/payment"
 78 |         )
 79 |     """
 80 | 
 81 |     amount_cents: int = Field(..., gt=0, description="Amount in cents (e.g., 10000 = R100.00)")
 82 |     currency: Literal["ZAR"] = Field(default="ZAR", description="Currency code (ZAR only for v1)")
 83 |     reference: str = Field(
 84 |         ..., min_length=1, max_length=100, description="Merchant-supplied idempotency key"
 85 |     )
 86 |     customer_email: EmailStr = Field(..., description="Customer email address")
 87 |     customer_name: str = Field(..., min_length=1, description="Customer full name")
 88 |     metadata: dict[str, str] = Field(
 89 |         default_factory=dict, description="Additional merchant data (max 10 keys)"
 90 |     )
 91 |     return_url: HttpUrl = Field(..., description="URL to redirect customer after success")
 92 |     cancel_url: HttpUrl = Field(..., description="URL to redirect customer after cancellation")
 93 |     webhook_url: HttpUrl = Field(..., description="URL to receive payment status webhooks")
 94 | 
 95 |     model_config = {"strict": True}
 96 | 
 97 | 
 98 | class PaymentResult(BaseModel):
 99 |     """
100 |     Result of a payment operation (create or refund).
101 |     
102 |     Example:
103 |         result = PaymentResult(
104 |             provider="payfast",
105 |             provider_payment_id="1234567",
106 |             reference="ORDER-123",
107 |             status=PaymentStatus.PENDING,
108 |             redirect_url="https://sandbox.payfast.co.za/eng/process?id=abc123",
109 |             raw={"m_payment_id": "1234567", "status": "PENDING"}
110 |         )
111 |     """
112 | 
113 |     provider: str = Field(..., description="Provider name (e.g., 'payfast')")
114 |     provider_payment_id: str = Field(..., description="Provider's internal payment ID")
115 |     reference: str = Field(..., description="Echoed from PaymentIntent")
116 |     status: PaymentStatus = Field(..., description="Current payment status")
117 |     redirect_url: HttpUrl | None = Field(
118 |         None, description="URL to redirect customer (for redirect-based flows)"
119 |     )
120 |     raw: dict[str, str | int | float | bool | None] = Field(
121 |         ..., description="Provider's untouched response for debugging"
122 |     )
123 | 
124 |     model_config = {"strict": True}
125 | 
126 | 
127 | class WebhookEvent(BaseModel):
128 |     """
129 |     Parsed and verified webhook event from a provider.
130 |     
131 |     This is returned by verify_webhook() after signature verification passes.
132 |     
133 |     Example:
134 |         event = WebhookEvent(
135 |             provider="payfast",
136 |             event_type="payment.succeeded",
137 |             provider_payment_id="1234567",
138 |             reference="ORDER-123",
139 |             amount_cents=10000,
140 |             raw={"m_payment_id": "1234567", "payment_status": "COMPLETE"},
141 |             received_at=datetime.now(timezone.utc)
142 |         )
143 |     """
144 | 
145 |     provider: str = Field(..., description="Provider name")
146 |     event_type: Literal["payment.succeeded", "payment.failed", "payment.refunded"] = Field(
147 |         ..., description="Normalized event type"
148 |     )
149 |     provider_payment_id: str = Field(..., description="Provider's payment ID")
150 |     reference: str = Field(..., description="Merchant reference from original intent")
151 |     amount_cents: int = Field(..., gt=0, description="Payment amount in cents")
152 |     raw: dict[str, str | int | float | bool | None] = Field(
153 |         ..., description="Provider's untouched webhook payload"
154 |     )
155 |     received_at: datetime = Field(..., description="When webhook was received (UTC)")
156 | 
157 |     model_config = {"strict": True}
158 | 
159 | 
160 | class BasePaymentAdapter(ABC):
161 |     """
162 |     Abstract base class for all payment provider adapters.
163 |     
164 |     Adapters must be:
165 |     - Stateless (config injected via constructor)
166 |     - Type-safe (full type hints, mypy --strict compliant)
167 |     - Money-safe (always use int cents, never floats)
168 |     - Security-conscious (constant-time signature comparison)
169 |     - Error-safe (catch all provider errors, re-raise as LekkerPayError subclasses)
170 |     
171 |     Example implementation:
172 |         class PayFastAdapter(BasePaymentAdapter):
173 |             provider_name = "payfast"
174 |             
175 |             def __init__(self, config: ProviderConfig) -> None:
176 |                 self.config = config
177 |                 self.client = httpx.AsyncClient(base_url=self._get_base_url())
178 |             
179 |             async def create_payment(self, intent: PaymentIntent) -> PaymentResult:
180 |                 # Implementation
181 |                 pass
182 |     """
183 | 
184 |     provider_name: ClassVar[str]
185 | 
186 |     @abstractmethod
187 |     def __init__(self, config: ProviderConfig) -> None:
188 |         """
189 |         Initialize adapter with provider configuration.
190 |         
191 |         Args:
192 |             config: Provider-specific configuration (API keys, sandbox flag, etc.)
193 |         """
194 |         pass
195 | 
196 |     @abstractmethod
197 |     async def create_payment(self, intent: PaymentIntent) -> PaymentResult:
198 |         """
199 |         Create a new payment with the provider.
200 |         
201 |         For redirect-based flows (PayFast, Ozow), this returns a redirect_url.
202 |         For API-based flows (Yoco), this may initiate the payment directly.
203 |         
204 |         Args:
205 |             intent: Provider-agnostic payment request
206 |             
207 |         Returns:
208 |             PaymentResult with provider_payment_id and redirect_url (if applicable)
209 |             
210 |         Raises:
211 |             AuthenticationError: Invalid credentials
212 |             InvalidRequestError: Invalid payment parameters
213 |             NetworkError: Provider communication failure
214 |             
215 |         Example:
216 |             result = await adapter.create_payment(intent)
217 |             # Redirect customer to result.redirect_url
218 |         """
219 |         pass
220 | 
221 |     @abstractmethod
222 |     async def get_status(self, provider_payment_id: str) -> PaymentStatus:
223 |         """
224 |         Query current status of a payment.
225 |         
226 |         Args:
227 |             provider_payment_id: Provider's internal payment ID
228 |             
229 |         Returns:
230 |             Current PaymentStatus
231 |             
232 |         Raises:
233 |             PaymentNotFoundError: Payment doesn't exist
234 |             AuthenticationError: Invalid credentials
235 |             NetworkError: Provider communication failure
236 |             
237 |         Example:
238 |             status = await adapter.get_status("1234567")
239 |             if status == PaymentStatus.SUCCEEDED:
240 |                 # Fulfill order
241 |         """
242 |         pass
243 | 
244 |     @abstractmethod
245 |     def verify_webhook(self, headers: Mapping[str, str], body: bytes) -> WebhookEvent:
246 |         """
247 |         Verify webhook signature and parse event.
248 |         
249 |         CRITICAL SECURITY REQUIREMENTS:
250 |         1. This method is SYNCHRONOUS (no async/await)
251 |         2. Signature comparison MUST use hmac.compare_digest (constant-time)
252 |         3. NEVER use == to compare signatures (timing attack vulnerability)
253 |         4. Body must be raw bytes for signature verification (don't parse first)
254 |         5. Raise SignatureMismatchError if verification fails
255 |         
256 |         Args:
257 |             headers: HTTP headers from webhook request (case-insensitive mapping)
258 |             body: Raw request body as bytes (not parsed JSON/form data)
259 |             
260 |         Returns:
261 |             Parsed and verified WebhookEvent
262 |             
263 |         Raises:
264 |             SignatureMismatchError: Signature verification failed
265 |             InvalidRequestError: Malformed webhook payload
266 |             
267 |         Example:
268 |             try:
269 |                 event = adapter.verify_webhook(request.headers, await request.body())
270 |                 # Process event (idempotency check in merchant-api layer)
271 |             except SignatureMismatchError:
272 |                 # Log and return 401
273 |                 pass
274 |         """
275 |         pass
276 | 
277 |     @abstractmethod
278 |     async def refund(
279 |         self, provider_payment_id: str, amount_cents: int | None = None
280 |     ) -> PaymentResult:
281 |         """
282 |         Refund a payment (full or partial).
283 |         
284 |         Args:
285 |             provider_payment_id: Provider's internal payment ID
286 |             amount_cents: Amount to refund in cents. If None, full refund.
287 |             
288 |         Returns:
289 |             PaymentResult with status=REFUNDED
290 |             
291 |         Raises:
292 |             PaymentNotFoundError: Payment doesn't exist
293 |             RefundError: Payment not refundable or amount exceeds original
294 |             InvalidRequestError: Provider doesn't support partial refunds
295 |             AuthenticationError: Invalid credentials
296 |             NetworkError: Provider communication failure
297 |             
298 |         Example:
299 |             # Full refund
300 |             result = await adapter.refund("1234567")
301 |             
302 |             # Partial refund (R50.00 of R100.00)
303 |             result = await adapter.refund("1234567", amount_cents=5000)
304 |         """
305 |         pass
306 | 
307 | # Made with Bob
</content>
</file>
<file><path>packages/lekker-pay/lekker_pay/router.py</path>
<content lines="1-195">
  1 | """
  2 | PaymentRouter - Factory for dispatching to provider adapters.
  3 | 
  4 | The router maintains a registry of provider adapters and their configurations,
  5 | allowing the merchant application to work with multiple providers through a
  6 | single interface.
  7 | """
  8 | 
  9 | from typing import Any
 10 | 
 11 | from lekker_pay.base import (
 12 |     BasePaymentAdapter,
 13 |     PaymentIntent,
 14 |     PaymentResult,
 15 |     PaymentStatus,
 16 |     ProviderConfig,
 17 |     WebhookEvent,
 18 | )
 19 | from lekker_pay.errors import InvalidRequestError
 20 | 
 21 | 
 22 | class PaymentRouter:
 23 |     """
 24 |     Factory and dispatcher for payment provider adapters.
 25 |     
 26 |     Example:
 27 |         config = {
 28 |             "payfast": ProviderConfig(
 29 |                 merchant_id="10000100",
 30 |                 merchant_key="46f0cd694581a",
 31 |                 passphrase="jt7NOE43FZPn",
 32 |                 sandbox=True
 33 |             ),
 34 |             "yoco": ProviderConfig(
 35 |                 api_key="sk_test_...",
 36 |                 webhook_secret="whsec_...",
 37 |                 sandbox=True
 38 |             )
 39 |         }
 40 |         
 41 |         router = PaymentRouter(config)
 42 |         
 43 |         # Create payment with specific provider
 44 |         result = await router.create_payment("payfast", intent)
 45 |         
 46 |         # Verify webhook (router auto-detects provider)
 47 |         event = router.verify_webhook("payfast", headers, body)
 48 |     """
 49 | 
 50 |     def __init__(self, provider_configs: dict[str, ProviderConfig]) -> None:
 51 |         """
 52 |         Initialize router with provider configurations.
 53 |         
 54 |         Args:
 55 |             provider_configs: Mapping of provider name to configuration
 56 |         """
 57 |         self._configs = provider_configs
 58 |         self._adapters: dict[str, BasePaymentAdapter] = {}
 59 |         self._adapter_classes: dict[str, type[BasePaymentAdapter]] = {}
 60 | 
 61 |     def register_adapter(
 62 |         self, provider_name: str, adapter_class: type[BasePaymentAdapter]
 63 |     ) -> None:
 64 |         """
 65 |         Register a provider adapter class.
 66 |         
 67 |         Args:
 68 |             provider_name: Provider identifier (e.g., "payfast")
 69 |             adapter_class: Adapter class (not instance)
 70 |             
 71 |         Example:
 72 |             router.register_adapter("payfast", PayFastAdapter)
 73 |         """
 74 |         self._adapter_classes[provider_name] = adapter_class
 75 | 
 76 |     def _get_adapter(self, provider_name: str) -> BasePaymentAdapter:
 77 |         """
 78 |         Get or create adapter instance for a provider.
 79 |         
 80 |         Args:
 81 |             provider_name: Provider identifier
 82 |             
 83 |         Returns:
 84 |             Adapter instance
 85 |             
 86 |         Raises:
 87 |             InvalidRequestError: Provider not configured or not registered
 88 |         """
 89 |         if provider_name not in self._adapters:
 90 |             if provider_name not in self._adapter_classes:
 91 |                 raise InvalidRequestError(
 92 |                     f"Provider '{provider_name}' not registered. "
 93 |                     f"Available providers: {', '.join(self._adapter_classes.keys())}"
 94 |                 )
 95 | 
 96 |             if provider_name not in self._configs:
 97 |                 raise InvalidRequestError(
 98 |                     f"Provider '{provider_name}' not configured. "
 99 |                     f"Configured providers: {', '.join(self._configs.keys())}"
100 |                 )
101 | 
102 |             adapter_class = self._adapter_classes[provider_name]
103 |             config = self._configs[provider_name]
104 |             self._adapters[provider_name] = adapter_class(config)
105 | 
106 |         return self._adapters[provider_name]
107 | 
108 |     async def create_payment(
109 |         self, provider_name: str, intent: PaymentIntent
110 |     ) -> PaymentResult:
111 |         """
112 |         Create payment with specified provider.
113 |         
114 |         Args:
115 |             provider_name: Provider to use (e.g., "payfast")
116 |             intent: Payment request
117 |             
118 |         Returns:
119 |             Payment result with redirect URL or payment details
120 |             
121 |         Example:
122 |             result = await router.create_payment("payfast", intent)
123 |             # Redirect customer to result.redirect_url
124 |         """
125 |         adapter = self._get_adapter(provider_name)
126 |         return await adapter.create_payment(intent)
127 | 
128 |     async def get_status(self, provider_name: str, provider_payment_id: str) -> PaymentStatus:
129 |         """
130 |         Query payment status from provider.
131 |         
132 |         Args:
133 |             provider_name: Provider identifier
134 |             provider_payment_id: Provider's payment ID
135 |             
136 |         Returns:
137 |             Current payment status
138 |         """
139 |         adapter = self._get_adapter(provider_name)
140 |         return await adapter.get_status(provider_payment_id)
141 | 
142 |     def verify_webhook(
143 |         self, provider_name: str, headers: dict[str, str], body: bytes
144 |     ) -> WebhookEvent:
145 |         """
146 |         Verify webhook signature and parse event.
147 |         
148 |         Args:
149 |             provider_name: Provider identifier
150 |             headers: HTTP headers from webhook request
151 |             body: Raw request body as bytes
152 |             
153 |         Returns:
154 |             Verified webhook event
155 |             
156 |         Raises:
157 |             SignatureMismatchError: Signature verification failed
158 |         """
159 |         adapter = self._get_adapter(provider_name)
160 |         return adapter.verify_webhook(headers, body)
161 | 
162 |     async def refund(
163 |         self,
164 |         provider_name: str,
165 |         provider_payment_id: str,
166 |         amount_cents: int | None = None,
167 |     ) -> PaymentResult:
168 |         """
169 |         Refund a payment (full or partial).
170 |         
171 |         Args:
172 |             provider_name: Provider identifier
173 |             provider_payment_id: Provider's payment ID
174 |             amount_cents: Amount to refund in cents (None = full refund)
175 |             
176 |         Returns:
177 |             Refund result
178 |         """
179 |         adapter = self._get_adapter(provider_name)
180 |         return await adapter.refund(provider_payment_id, amount_cents)
181 | 
182 |     def list_providers(self) -> list[str]:
183 |         """
184 |         List all registered and configured providers.
185 |         
186 |         Returns:
187 |             List of provider names
188 |         """
189 |         return [
190 |             name
191 |             for name in self._adapter_classes.keys()
192 |             if name in self._configs
193 |         ]
194 | 
195 | # Made with Bob
</content>
</file>
<file><path>packages/lekker-pay/lekker_pay/errors.py</path>
<content lines="1-112">
  1 | """
  2 | Unified exception hierarchy for Lekker Pay.
  3 | 
  4 | All provider-specific errors must be caught and re-raised as one of these exceptions.
  5 | Never let raw httpx.HTTPError or provider-specific exceptions escape the adapter boundary.
  6 | """
  7 | 
  8 | 
  9 | class LekkerPayError(Exception):
 10 |     """Base exception for all Lekker Pay errors."""
 11 | 
 12 |     def __init__(self, message: str, provider: str | None = None) -> None:
 13 |         self.message = message
 14 |         self.provider = provider
 15 |         super().__init__(message)
 16 | 
 17 | 
 18 | class ProviderError(LekkerPayError):
 19 |     """Base class for provider-specific errors."""
 20 | 
 21 |     pass
 22 | 
 23 | 
 24 | class AuthenticationError(ProviderError):
 25 |     """
 26 |     Raised when provider authentication fails.
 27 |     
 28 |     Examples:
 29 |     - Invalid API key
 30 |     - Invalid merchant ID
 31 |     - Expired credentials
 32 |     """
 33 | 
 34 |     pass
 35 | 
 36 | 
 37 | class InvalidRequestError(ProviderError):
 38 |     """
 39 |     Raised when the request to the provider is invalid.
 40 |     
 41 |     Examples:
 42 |     - Missing required fields
 43 |     - Invalid amount format
 44 |     - Unsupported currency
 45 |     - Provider doesn't support partial refunds
 46 |     """
 47 | 
 48 |     pass
 49 | 
 50 | 
 51 | class NetworkError(ProviderError):
 52 |     """
 53 |     Raised when network communication with the provider fails.
 54 |     
 55 |     Examples:
 56 |     - Connection timeout
 57 |     - DNS resolution failure
 58 |     - Provider service unavailable
 59 |     """
 60 | 
 61 |     pass
 62 | 
 63 | 
 64 | class SignatureMismatchError(ProviderError):
 65 |     """
 66 |     Raised when webhook signature verification fails.
 67 |     
 68 |     CRITICAL: This must use constant-time comparison (hmac.compare_digest).
 69 |     Never use == to compare signatures.
 70 |     """
 71 | 
 72 |     pass
 73 | 
 74 | 
 75 | class RateLimitError(ProviderError):
 76 |     """
 77 |     Raised when provider rate limit is exceeded.
 78 |     
 79 |     Should include retry-after information if available.
 80 |     """
 81 | 
 82 |     def __init__(
 83 |         self,
 84 |         message: str,
 85 |         provider: str | None = None,
 86 |         retry_after_seconds: int | None = None,
 87 |     ) -> None:
 88 |         super().__init__(message, provider)
 89 |         self.retry_after_seconds = retry_after_seconds
 90 | 
 91 | 
 92 | class PaymentNotFoundError(ProviderError):
 93 |     """
 94 |     Raised when attempting to query or refund a payment that doesn't exist.
 95 |     """
 96 | 
 97 |     pass
 98 | 
 99 | 
100 | class RefundError(ProviderError):
101 |     """
102 |     Raised when a refund operation fails.
103 |     
104 |     Examples:
105 |     - Payment not in refundable state
106 |     - Refund amount exceeds original payment
107 |     - Provider-specific refund restrictions
108 |     """
109 | 
110 |     pass
111 | 
112 | # Made with Bob
</content>
</file>
<file><path>compose.yml</path>
<content lines="1-62">
 1 | version: '3.9'
 2 | 
 3 | services:
 4 |   postgres:
 5 |     image: postgres:16-alpine
 6 |     container_name: lekker-pay-postgres
 7 |     environment:
 8 |       POSTGRES_DB: lekker_pay
 9 |       POSTGRES_USER: lekker_pay
10 |       POSTGRES_PASSWORD: lekker_pay_dev
11 |     ports:
12 |       - "5432:5432"
13 |     volumes:
14 |       - postgres_data:/var/lib/postgresql/data
15 |     healthcheck:
16 |       test: ["CMD-SHELL", "pg_isready -U lekker_pay"]
17 |       interval: 5s
18 |       timeout: 5s
19 |       retries: 5
20 | 
21 |   redis:
22 |     image: redis:7-alpine
23 |     container_name: lekker-pay-redis
24 |     ports:
25 |       - "6379:6379"
26 |     volumes:
27 |       - redis_data:/data
28 |     healthcheck:
29 |       test: ["CMD", "redis-cli", "ping"]
30 |       interval: 5s
31 |       timeout: 3s
32 |       retries: 5
33 | 
34 |   merchant-api:
35 |     build:
36 |       context: ./apps/merchant-api
37 |       dockerfile: Dockerfile
38 |     container_name: lekker-pay-api
39 |     environment:
40 |       DATABASE_URL: postgresql+asyncpg://lekker_pay:lekker_pay_dev@postgres:5432/lekker_pay
41 |       REDIS_URL: redis://redis:6379/0
42 |       PAYFAST_MERCHANT_ID: "10000100"
43 |       PAYFAST_MERCHANT_KEY: "46f0cd694581a"
44 |       PAYFAST_PASSPHRASE: "jt7NOE43FZPn"
45 |       PAYFAST_SANDBOX: "true"
46 |     ports:
47 |       - "8000:8000"
48 |     depends_on:
49 |       postgres:
50 |         condition: service_healthy
51 |       redis:
52 |         condition: service_healthy
53 |     volumes:
54 |       - ./apps/merchant-api:/app
55 |       - ./packages/lekker-pay:/packages/lekker-pay
56 |     command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
57 | 
58 | volumes:
59 |   postgres_data:
60 |   redis_data:
61 | 
62 | # Made with Bob
</content>
</file>
</files>
<environment_details>
# VSCode Visible Files


# VSCode Open Tabs
package.json,pnpm-workspace.yaml,packages/lekker-pay/pyproject.toml,packages/lekker-pay/README.md,packages/lekker-pay/lekker_pay/errors.py,packages/lekker-pay/lekker_pay/base.py,packages/lekker-pay/lekker_pay/router.py,packages/lekker-pay/lekker_pay/__init__.py,packages/lekker-pay/lekker_pay/providers/__init__.py,packages/lekker-pay/tests/__init__.py,packages/lekker-pay/tests/conftest.py,docs/ARCHITECTURE.md,docs/providers/payfast.md,docs/providers/ozow.md,docs/providers/yoco.md,compose.yml

# Current Time
Current time in ISO 8601 UTC format: 2026-05-15T16:16:18.030Z
User time zone: Africa/Johannesburg, UTC+2:00

# Current Cost
$0.03

# Review Exclusions
The following file patterns are excluded from code reviews:
- .vscode/**
- .env
- secrets/

# Current Mode
<slug>code</slug>
<name>💻 Code</name>
You have not created a todo list yet. Create one with `update_todo_list` if your task is complicated or involves multiple steps.
</environment_details>

---

**Assistant:**

<read_file>
<args>
<file>
<path>docs/providers/payfast.md</path>
</file>
<file>
<path>docs/providers/ozow.md</path>
</file>
<file>
<path>docs/providers/yoco.md</path>
</file>
<file>
<path>packages/lekker-pay/tests/conftest.py</path>
</file>
<file>
<path>pnpm-workspace.yaml</path>
</file>
</args>
</read_file>

---

**User:**

[read_file for 5 files] Result:
<files>
<file><path>docs/providers/payfast.md</path>
<content lines="1-98">
 1 | # PayFast Integration Guide
 2 | 
 3 | ## Overview
 4 | 
 5 | PayFast is a South African payment gateway that uses a redirect-based flow with MD5 signature verification.
 6 | 
 7 | ## Authentication
 8 | 
 9 | - **Merchant ID**: Unique identifier for your PayFast account
10 | - **Merchant Key**: Secret key for signature generation
11 | - **Passphrase**: Additional secret for enhanced security (optional but recommended)
12 | 
13 | ## API Endpoints
14 | 
15 | ### Sandbox
16 | - Payment: `https://sandbox.payfast.co.za/eng/process`
17 | - Validation: `https://sandbox.payfast.co.za/eng/query/validate`
18 | 
19 | ### Production
20 | - Payment: `https://www.payfast.co.za/eng/process`
21 | - Validation: `https://www.payfast.co.za/eng/query/validate`
22 | 
23 | ## Payment Flow
24 | 
25 | 1. **Create Payment**: POST form-encoded data to `/eng/process`
26 | 2. **Customer Redirect**: PayFast redirects customer to payment page
27 | 3. **ITN Webhook**: PayFast POSTs payment status to your webhook URL
28 | 4. **Server Validation**: Your server validates ITN by POSTing back to `/eng/query/validate`
29 | 
30 | ## Signature Generation (MD5)
31 | 
32 | PayFast uses MD5 signatures over alphabetically-sorted parameters:
33 | 
34 | ```python
35 | import hashlib
36 | from urllib.parse import urlencode
37 | 
38 | def generate_signature(data: dict, passphrase: str) -> str:
39 |     # Remove signature field if present
40 |     data = {k: v for k, v in data.items() if k != 'signature' and v}
41 |     
42 |     # Sort alphabetically and URL encode
43 |     sorted_params = sorted(data.items())
44 |     param_string = urlencode(sorted_params)
45 |     
46 |     # Append passphrase
47 |     param_string += f"&passphrase={passphrase}"
48 |     
49 |     # MD5 hash
50 |     return hashlib.md5(param_string.encode()).hexdigest()
51 | ```
52 | 
53 | ## ITN (Instant Transaction Notification)
54 | 
55 | PayFast sends a POST request to your webhook URL with payment details:
56 | 
57 | **Headers**: `Content-Type: application/x-www-form-urlencoded`
58 | 
59 | **Body Parameters**:
60 | - `m_payment_id`: Your reference
61 | - `pf_payment_id`: PayFast's payment ID
62 | - `payment_status`: `COMPLETE`, `FAILED`, or `CANCELLED`
63 | - `amount_gross`: Payment amount (string, e.g., "100.00")
64 | - `signature`: MD5 signature
65 | 
66 | **Verification Steps**:
67 | 1. Verify signature matches (constant-time comparison)
68 | 2. Verify payment status
69 | 3. POST data back to `/eng/query/validate` to confirm authenticity
70 | 4. Check response is "VALID"
71 | 
72 | ## Status Mapping
73 | 
74 | | PayFast Status | Lekker Pay Status |
75 | |----------------|-------------------|
76 | | `COMPLETE`     | `SUCCEEDED`       |
77 | | `FAILED`       | `FAILED`          |
78 | | `CANCELLED`    | `CANCELLED`       |
79 | 
80 | ## Error Handling
81 | 
82 | - **400**: Invalid request parameters
83 | - **401**: Invalid merchant credentials
84 | - **500**: PayFast server error
85 | 
86 | ## Testing
87 | 
88 | Use sandbox credentials:
89 | - Merchant ID: `10000100`
90 | - Merchant Key: `46f0cd694581a`
91 | - Passphrase: `jt7NOE43FZPn`
92 | 
93 | Test card: Any valid card number in sandbox mode
94 | 
95 | ## References
96 | 
97 | - [PayFast API Documentation](https://developers.payfast.co.za/)
98 | - [ITN Guide](https://developers.payfast.co.za/docs#instant_transaction_notification)
</content>
</file>
<file><path>docs/providers/ozow.md</path>
<content lines="1-80">
 1 | # Ozow Integration Guide
 2 | 
 3 | ## Overview
 4 | 
 5 | Ozow is a South African instant EFT payment provider using SHA512 signature verification.
 6 | 
 7 | ## Authentication
 8 | 
 9 | - **Site Code**: Your Ozow site identifier
10 | - **API Key**: Private key for API authentication
11 | - **Private Key**: Secret key for signature generation
12 | 
13 | ## API Endpoints
14 | 
15 | ### Sandbox
16 | - Payment: `https://pay.sandbox.ozow.com`
17 | 
18 | ### Production
19 | - Payment: `https://pay.ozow.com`
20 | 
21 | ## Payment Flow
22 | 
23 | 1. **Create Payment**: POST to Ozow with signed request
24 | 2. **Customer Redirect**: Redirect customer to Ozow payment page
25 | 3. **Notification**: Ozow POSTs payment status to your notification URL
26 | 4. **Status Query**: Optional server-to-server status check
27 | 
28 | ## Signature Generation (SHA512)
29 | 
30 | Ozow uses SHA512 hash of concatenated fields in specific order:
31 | 
32 | ```python
33 | import hashlib
34 | 
35 | def generate_signature(site_code: str, country_code: str, currency_code: str,
36 |                       amount: str, transaction_ref: str, bank_ref: str,
37 |                       optional1: str, optional2: str, optional3: str,
38 |                       optional4: str, optional5: str, cancel_url: str,
39 |                       error_url: str, success_url: str, notify_url: str,
40 |                       is_test: str, private_key: str) -> str:
41 |     
42 |     input_string = (
43 |         f"{site_code}{country_code}{currency_code}{amount}"
44 |         f"{transaction_ref}{bank_ref}{optional1}{optional2}"
45 |         f"{optional3}{optional4}{optional5}{cancel_url}"
46 |         f"{error_url}{success_url}{notify_url}{is_test}"
47 |     ).lower()
48 |     
49 |     hash_input = input_string + private_key.lower()
50 |     return hashlib.sha512(hash_input.encode()).hexdigest()
51 | ```
52 | 
53 | ## Notification Webhook
54 | 
55 | Ozow POSTs to your notification URL with payment status:
56 | 
57 | **Parameters**:
58 | - `SiteCode`: Your site code
59 | - `TransactionId`: Ozow's transaction ID
60 | - `TransactionReference`: Your reference
61 | - `Amount`: Payment amount
62 | - `Status`: Payment status
63 | - `Hash`: SHA512 signature
64 | 
65 | ## Status Mapping
66 | 
67 | | Ozow Status | Lekker Pay Status |
68 | |-------------|-------------------|
69 | | `Complete`  | `SUCCEEDED`       |
70 | | `Cancelled` | `CANCELLED`       |
71 | | `Error`     | `FAILED`          |
72 | | `Pending`   | `PENDING`         |
73 | 
74 | ## Testing
75 | 
76 | Sandbox mode: Set `IsTest=true` in request
77 | 
78 | ## References
79 | 
80 | - [Ozow API Documentation](https://docs.ozow.com/)
</content>
</file>
<file><path>docs/providers/yoco.md</path>
<content lines="1-132">
  1 | # Yoco Integration Guide
  2 | 
  3 | ## Overview
  4 | 
  5 | Yoco is a modern South African payment provider with REST API and HMAC-SHA256 webhook signatures.
  6 | 
  7 | ## Authentication
  8 | 
  9 | - **API Key**: Bearer token for API requests (starts with `sk_live_` or `sk_test_`)
 10 | - **Webhook Secret**: Secret for HMAC signature verification (starts with `whsec_`)
 11 | 
 12 | ## API Endpoints
 13 | 
 14 | ### Sandbox
 15 | - Base URL: `https://payments.yoco.com/api`
 16 | - Checkouts: `POST /checkouts`
 17 | 
 18 | ### Production
 19 | - Same as sandbox (use production API key)
 20 | 
 21 | ## Payment Flow
 22 | 
 23 | 1. **Create Checkout**: POST to `/api/checkouts` with bearer token
 24 | 2. **Customer Redirect**: Redirect customer to `redirectUrl` from response
 25 | 3. **Webhook**: Yoco POSTs payment events to your webhook URL
 26 | 4. **Status Query**: GET `/api/checkouts/{id}` to query status
 27 | 
 28 | ## API Request
 29 | 
 30 | ```http
 31 | POST /api/checkouts
 32 | Authorization: Bearer sk_test_...
 33 | Content-Type: application/json
 34 | 
 35 | {
 36 |   "amount": 10000,
 37 |   "currency": "ZAR",
 38 |   "cancelUrl": "https://example.com/cancel",
 39 |   "successUrl": "https://example.com/success",
 40 |   "failureUrl": "https://example.com/failure",
 41 |   "metadata": {
 42 |     "reference": "ORDER-123"
 43 |   }
 44 | }
 45 | ```
 46 | 
 47 | ## Webhook Signature (HMAC-SHA256)
 48 | 
 49 | **CRITICAL**: Signature is computed over raw request body bytes.
 50 | 
 51 | ```python
 52 | import hmac
 53 | import hashlib
 54 | 
 55 | def verify_signature(webhook_secret: str, body: bytes, signature: str) -> bool:
 56 |     expected = hmac.new(
 57 |         webhook_secret.encode(),
 58 |         body,
 59 |         hashlib.sha256
 60 |     ).hexdigest()
 61 |     
 62 |     # MUST use constant-time comparison
 63 |     return hmac.compare_digest(expected, signature)
 64 | ```
 65 | 
 66 | **Headers**:
 67 | - `Webhook-Signature`: HMAC-SHA256 hex digest
 68 | 
 69 | **Body**: JSON payload (must be raw bytes for verification)
 70 | 
 71 | ```json
 72 | {
 73 |   "type": "payment.succeeded",
 74 |   "payload": {
 75 |     "id": "ch_...",
 76 |     "status": "succeeded",
 77 |     "amount": 10000,
 78 |     "currency": "ZAR",
 79 |     "metadata": {
 80 |       "reference": "ORDER-123"
 81 |     }
 82 |   }
 83 | }
 84 | ```
 85 | 
 86 | ## Event Types
 87 | 
 88 | - `payment.succeeded`: Payment completed successfully
 89 | - `payment.failed`: Payment failed
 90 | - `payment.refunded`: Payment was refunded
 91 | 
 92 | ## Status Mapping
 93 | 
 94 | | Yoco Status | Lekker Pay Status |
 95 | |-------------|-------------------|
 96 | | `succeeded` | `SUCCEEDED`       |
 97 | | `failed`    | `FAILED`          |
 98 | | `pending`   | `PENDING`         |
 99 | | `refunded`  | `REFUNDED`        |
100 | 
101 | ## Error Handling
102 | 
103 | - **401**: Invalid API key
104 | - **400**: Invalid request (check error message)
105 | - **404**: Checkout not found
106 | - **429**: Rate limit exceeded
107 | 
108 | ## Refunds
109 | 
110 | ```http
111 | POST /api/refunds
112 | Authorization: Bearer sk_test_...
113 | Content-Type: application/json
114 | 
115 | {
116 |   "checkoutId": "ch_...",
117 |   "amount": 5000  // Optional, omit for full refund
118 | }
119 | ```
120 | 
121 | ## Testing
122 | 
123 | Use test API key: `sk_test_...`
124 | 
125 | Test cards:
126 | - Success: `4242 4242 4242 4242`
127 | - Decline: `4000 0000 0000 0002`
128 | 
129 | ## References
130 | 
131 | - [Yoco API Documentation](https://developer.yoco.com/)
132 | - [Webhook Guide](https://developer.yoco.com/webhooks)
</content>
</file>
<file><path>packages/lekker-pay/tests/conftest.py</path>
<content lines="1-44">
 1 | """
 2 | Pytest configuration and shared fixtures for lekker-pay tests.
 3 | """
 4 | 
 5 | import pytest
 6 | from datetime import datetime, timezone
 7 | from pydantic import HttpUrl
 8 | 
 9 | from lekker_pay import PaymentIntent, ProviderConfig
10 | 
11 | 
12 | @pytest.fixture
13 | def sample_config() -> ProviderConfig:
14 |     """Sample provider configuration for testing."""
15 |     return ProviderConfig(
16 |         merchant_id="10000100",
17 |         merchant_key="46f0cd694581a",
18 |         passphrase="jt7NOE43FZPn",
19 |         sandbox=True,
20 |     )
21 | 
22 | 
23 | @pytest.fixture
24 | def sample_intent() -> PaymentIntent:
25 |     """Sample payment intent for testing."""
26 |     return PaymentIntent(
27 |         amount_cents=10000,  # R100.00
28 |         currency="ZAR",
29 |         reference="TEST-ORDER-123",
30 |         customer_email="test@example.com",
31 |         customer_name="Test Customer",
32 |         return_url=HttpUrl("https://example.com/success"),
33 |         cancel_url=HttpUrl("https://example.com/cancel"),
34 |         webhook_url=HttpUrl("https://example.com/webhooks/payment"),
35 |         metadata={"order_id": "123", "customer_id": "456"},
36 |     )
37 | 
38 | 
39 | @pytest.fixture
40 | def utc_now() -> datetime:
41 |     """Current UTC datetime for testing."""
42 |     return datetime.now(timezone.utc)
43 | 
44 | # Made with Bob
</content>
</file>
<file><path>pnpm-workspace.yaml</path>
<content lines="1-5">
1 | packages:
2 |   - 'apps/*'
3 |   - 'packages/*'
4 | 
5 | # Made with Bob
</content>
</file>
</files>
<environment_details>
# VSCode Visible Files


# VSCode Open Tabs
package.json,pnpm-workspace.yaml,packages/lekker-pay/pyproject.toml,packages/lekker-pay/README.md,packages/lekker-pay/lekker_pay/errors.py,packages/lekker-pay/lekker_pay/base.py,packages/lekker-pay/lekker_pay/router.py,packages/lekker-pay/lekker_pay/__init__.py,packages/lekker-pay/lekker_pay/providers/__init__.py,packages/lekker-pay/tests/__init__.py,packages/lekker-pay/tests/conftest.py,docs/ARCHITECTURE.md,docs/providers/payfast.md,docs/providers/ozow.md,docs/providers/yoco.md,compose.yml

# Current Time
Current time in ISO 8601 UTC format: 2026-05-15T16:16:25.023Z
User time zone: Africa/Johannesburg, UTC+2:00

# Current Cost
$0.08

# Review Exclusions
The following file patterns are excluded from code reviews:
- .vscode/**
- .env
- secrets/

# Current Mode
<slug>code</slug>
<name>💻 Code</name>
You have not created a todo list yet. Create one with `update_todo_list` if your task is complicated or involves multiple steps.
</environment_details>

---

**Assistant:**

<attempt_completion>
<result>
# Detailed Explanation of Lekker Pay Project

## Project Overview
**Lekker Pay** is a unified payment adapter library designed for South African payment providers, created as an IBM BOB Hackathon project. It provides a single, consistent interface for integrating with multiple SA payment gateways (PayFast, Ozow, and Yoco).

## Core Architecture

### 1. **Design Philosophy**
The project follows three fundamental principles:
- **Provider Agnosticism**: One interface works with multiple payment providers
- **Type Safety**: Strict typing using Pydantic v2 and mypy compliance
- **Security First**: Constant-time signature verification and integer-based money handling

### 2. **Project Structure**
```
lekker-pay-za/
├── packages/lekker-pay/          # Core Python library
│   ├── lekker_pay/
│   │   ├── __init__.py           # Public API exports
│   │   ├── base.py               # Abstract base class & models
│   │   ├── router.py             # Provider dispatcher/factory
│   │   ├── errors.py             # Exception hierarchy
│   │   └── providers/            # Provider implementations
│   └── tests/                    # Test suite
├── docs/                         # Documentation
│   ├── ARCHITECTURE.md           # System design
│   └── providers/                # Provider-specific guides
└── compose.yml                   # Docker development environment
```

### 3. **Core Components**

#### **BasePaymentAdapter (Abstract Base Class)**
- Defines the contract all provider adapters must implement
- Four key methods:
  - `create_payment()`: Initiate a payment
  - `get_status()`: Query payment status
  - `verify_webhook()`: Verify and parse webhook events
  - `refund()`: Process refunds (full or partial)
- Stateless design with config injection
- All I/O operations are async except webhook verification

#### **PaymentRouter (Factory & Dispatcher)**
- Manages provider registration and configuration
- Lazy instantiation of adapters (created on first use)
- Provides unified error handling
- Routes requests to appropriate provider adapter

#### **Pydantic Models**
Five core models with strict validation:
- **PaymentIntent**: Provider-agnostic payment request
- **PaymentResult**: Unified payment response
- **WebhookEvent**: Verified webhook payload
- **ProviderConfig**: Provider credentials/settings
- **PaymentStatus**: Enum for payment states (PENDING, PROCESSING, SUCCEEDED, FAILED, REFUNDED, CANCELLED)

#### **Error Hierarchy**
Structured exception system:
```
LekkerPayError (base)
└── ProviderError
    ├── AuthenticationError
    ├── InvalidRequestError
    ├── NetworkError
    ├── SignatureMismatchError
    ├── RateLimitError
    ├── PaymentNotFoundError
    └── RefundError
```

### 4. **Security Features**

#### **Money Handling**
- **CRITICAL**: All amounts are integers in cents (never floats)
- Example: R100.00 = 10000 cents
- Prevents floating-point precision issues

#### **Webhook Signature Verification**
- Uses `hmac.compare_digest()` for constant-time comparison
- Prevents timing attack vulnerabilities
- Raw bytes required for signature computation
- Synchronous operation (no async overhead for crypto)

### 5. **Supported Providers**

#### **PayFast**
- Redirect-based flow with MD5 signatures
- ITN (Instant Transaction Notification) webhooks
- Server-side validation required
- Sandbox credentials provided

#### **Ozow**
- Instant EFT provider
- SHA512 signature verification
- Specific field concatenation order for signatures

#### **Yoco**
- Modern REST API
- HMAC-SHA256 webhook signatures
- Supports refunds via API
- Bearer token authentication

### 6. **Development Environment**

#### **Docker Compose Setup**
Three services configured:
- **PostgreSQL 16**: Database for merchant application
- **Redis 7**: Caching and idempotency checks
- **Merchant API**: FastAPI application (placeholder)

#### **Technology Stack**
- **Python 3.12+**: Core language
- **Pydantic v2**: Data validation and serialization
- **httpx**: Async HTTP client
- **cryptography**: Secure operations
- **structlog**: Structured logging
- **pytest**: Testing framework with async support
- **respx**: HTTP mocking for tests
- **mypy**: Static type checking
- **ruff**: Linting and formatting

### 7. **Key Design Decisions**

#### **Stateless Adapters**
- Configuration injected via constructor
- No environment variable reads inside adapters
- Easier testing and dependency injection

#### **Async by Default**
- All I/O operations are async
- Better performance for concurrent operations
- Webhook verification is sync (crypto doesn't need async)

#### **Type Safety**
- No `Any` types in public interfaces
- Strict mode enabled for all Pydantic models
- Full mypy compliance with `--strict` flag

#### **Error Boundary**
- Adapters catch all provider-specific exceptions
- Re-raise as appropriate LekkerPayError subclass
- Never let raw httpx.HTTPError escape

### 8. **Testing Strategy**
- Unit tests with respx HTTP mocking
- Fixtures for common test data
- Coverage reporting configured
- Integration tests (optional, env-gated)

### 9. **Documentation**
Comprehensive documentation includes:
- Architecture overview with Mermaid diagrams
- Provider-specific integration guides
- Security best practices
- Code examples and usage patterns
- Testing guidelines

### 10. **Monorepo Structure**
- Uses pnpm workspaces for package management
- Supports multiple apps and packages
- Shared configuration and dependencies
- Scripts for development, build, test, and lint

## Current State
The project has a **complete foundational architecture** with:
- ✅ Core abstractions defined
- ✅ Type-safe models implemented
- ✅ Error hierarchy established
- ✅ Router/dispatcher implemented
- ✅ Comprehensive documentation
- ✅ Development environment configured
- ✅ Testing infrastructure set up
- ⏳ Provider implementations (to be completed)
- ⏳ Merchant API application (placeholder)

This is a well-architected, production-ready foundation for a payment abstraction library focused on the South African market.
</result>
</attempt_completion>

