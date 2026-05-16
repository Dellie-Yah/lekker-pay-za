# Bob Prompt — Implement the Paystack Adapter

Copy everything below the line into Bob.

---

# Task: Implement the `Paystack` adapter for Lekker Pay

You are adding the Paystack payment provider to the Lekker Pay library. This is **not isolated code generation** — the adapter must integrate end-to-end through `apps/merchant-api/` so a real Paystack sandbox payment can be processed (test card `4084 0840 8408 4081`, PIN `0000`, OTP `123456`). Treat the contract, the recipe, and the PayFast reference as binding law.

Paystack expands Lekker Pay beyond SA-only providers — it is pan-African (Nigeria, Ghana, Kenya, South Africa, Côte d'Ivoire) and structurally very different from PayFast (modern REST, no redirect form, Bearer auth, JSON everywhere).

## Read first, in this exact order, before writing any code

1. `packages/lekker-pay/lekker_pay/base.py` — the `BasePaymentAdapter` contract and Pydantic types
2. `packages/lekker-pay/lekker_pay/errors.py` — the exception hierarchy you MUST raise from
3. `packages/lekker-pay/lekker_pay/providers/payfast.py` — the canonical reference adapter (99% coverage)
4. `packages/lekker-pay/tests/test_payfast.py` — the test patterns and footgun regressions
5. `docs/PAYFAST_DESIGN_RATIONALE.md` — the WHY behind every PayFast decision (read in full)
6. `docs/PROVIDER_RECIPE.md` — the procedural checklist and quality gates
7. `docs/providers/paystack.md` — Paystack's API documentation (already saved)
8. `apps/merchant-api/app/payment_service.py` — the integration surface you will extend
9. `apps/merchant-api/app/config.py` — the env-loading pattern (pydantic-settings)
10. `apps/merchant-api/app/main.py` — the webhook handler that calls `verify_webhook`

**Confirmation step (do this first, before producing a plan):**
- List back the three things you consider most important from `PAYFAST_DESIGN_RATIONALE.md`
- Identify the Paystack-specific equivalent of PayFast's empty-passphrase bug. (Hint: think about the secret-key/webhook-secret duality — see "Critical Footgun" below)

## Config rule (binding)

Use the **generic `ProviderConfig`** from `lekker_pay.base` — the same one PayFast uses in `apps/merchant-api/app/payment_service.py`. Do NOT create a `PaystackConfig` dataclass or Pydantic model. Paystack populates only:

```python
config = ProviderConfig(
    api_key="sk_test_...",   # the Paystack secret key
    sandbox=True,
)
```

The adapter's `__init__` validates that `config.api_key` is present and raises `ValueError` if missing. Other `ProviderConfig` fields (merchant_id, passphrase, etc.) stay `None` — that is the intended design. Mirror PayFast's pattern in `payment_service.py` exactly. Do not refactor PayFast in this pass; the shipped E2E milestone (`feat: lekker-pay v0.1 with PayFast end-to-end working`) must not break.

## Paystack — Provider Facts (verified against `docs/providers/paystack.md`)

```
Provider name:           Paystack
Module slug:             paystack
Flow type:               REST-API + redirect (initialize returns authorization_url; customer is sent there)
Auth scheme:             Bearer token in Authorization header
Signature algorithm:     HMAC-SHA512
Signature location:      HTTP header  x-paystack-signature
Signature input:         RAW BYTES of the webhook request body (NOT parsed JSON)
Signature key:           THE SAME secret key used for API Bearer auth  ⚠ FOOTGUN — see below
Webhook secret distinct
  from API key?          NO — one secret_key value does both jobs
Server-side verify API:  GET /transaction/verify/{reference}
                          → exposed as a separate async method `verify_transaction()`,
                            NOT folded into verify_webhook()
Currency parameter:      REQUIRED in request, default ZAR
Amount unit:             integer cents/kobo INTERNALLY
                          → ON THE WIRE (initialize):  amount is sent as a STRING ("10000")
                          → ON THE WIRE (webhook/verify): amount comes back as an INTEGER (10000)
                          → ON THE WIRE (refund): amount is an INTEGER in cents
                            (this string-vs-integer split is a real footgun — write a test)
Sandbox base URL:        https://api.paystack.co
Live base URL:           https://api.paystack.co  (same host — environment switched via sk_test_ vs sk_live_ key)
Initialize endpoint:     POST /transaction/initialize
Verify endpoint:         GET  /transaction/verify/{reference}
Refund endpoint:         POST /refund
Redirect URL field:      response.data.authorization_url   (NOT access_code)
Event types:             charge.success | charge.failed | refund.processed
```

## Critical Footgun for Paystack (the analogue of PayFast's empty-passphrase)

Paystack's secret_key is used **for two distinct purposes**:
1. As a Bearer token in `Authorization: Bearer sk_test_...` for outbound API calls
2. As the HMAC-SHA512 key for verifying inbound webhook signatures

These are the **same value** but they are **logically distinct uses**. Footguns:
- A test environment may rotate the secret_key. Cached/old keys silently break webhooks while API calls still work (or vice versa).
- If a future Paystack release ever introduces a distinct webhook secret, code that conflates the two will silently break.
- A merchant copying configs across environments may put the live `sk_live_` key in a sandbox slot — Bearer calls fail loudly (401) but webhook verification silently succeeds against the wrong signatures.

**Mitigation:** Paystack stores its secret in `ProviderConfig.api_key`. The adapter uses the **same** `config.api_key` value as both the Bearer token AND the HMAC-SHA512 key — this duality is intentional but must be documented in code with an inline comment at each use site. In `verify_webhook`, log a low-volume `info` event recording that signature verification ran (without logging the key itself). Write the regression test `test_paystack_api_key_used_for_both_bearer_and_webhook_hmac`.

## Status mapping (Paystack → PaymentStatus)

```
"success"   → SUCCEEDED
"failed"    → FAILED
"abandoned" → FAILED       (customer left, treat as failure for unified semantics)
"pending"   → PENDING
unknown     → raise InvalidRequestError  ("Unknown Paystack status: {value}")
```

## Webhook event mapping (Paystack `event` field → WebhookEvent.event_type)

```
"charge.success"   → "payment.succeeded"
"charge.failed"    → "payment.failed"
"refund.processed" → "payment.refunded"
unknown event      → raise InvalidRequestError
```

## What you are building (artefacts checklist)

1. `packages/lekker-pay/lekker_pay/providers/paystack.py`
2. `packages/lekker-pay/tests/test_paystack.py`
3. Updates to:
   - `packages/lekker-pay/lekker_pay/providers/__init__.py` — export `PaystackAdapter`
   - `packages/lekker-pay/lekker_pay/__init__.py` — top-level re-export
   - `apps/merchant-api/app/config.py` — add `paystack_secret_key: str = Field(default="", ...)`
   - `apps/merchant-api/app/payment_service.py` — register `PaystackAdapter` in the router
   - `apps/merchant-api/app/main.py` — ensure `/checkout` HTML form has Paystack option in the provider dropdown
   - `.env.example` — add `PAYSTACK_SECRET_KEY=` line (empty value, never the real secret)
   - `docs/PROVIDER_RECIPE.md` — capture new patterns invented (REST flow, raw-body HMAC on FastAPI, string/integer amount duality)

## Hard rules — non-negotiable

## Config rule
- Use the existing `ProviderConfig` Pydantic model from `lekker_pay.base`.
- Paystack needs only: api_key (the sk_test_/sk_live_ secret), sandbox.
- Mirror exactly how PayFast does it in `payment_service.py`.
- Do NOT create a `PaystackConfig` dataclass.

### Money
- Internally always `int` cents. Negative amounts raise `InvalidRequestError`.
- For `/transaction/initialize`: convert to **string** via `str(amount_cents)`.
- For `/refund`: send as **integer** `amount_cents`.
- For incoming webhook/verify responses: amount is already an integer in cents — no conversion needed.
- Use `Decimal` if any rand-string parsing is ever needed (it isn't, for Paystack — different from PayFast). Never `float`.

### Signatures
- `hmac.compare_digest` for every signature comparison. Writing `==` between signature strings is a failure.
- HMAC-SHA512 over the **raw request body bytes** with `config.secret_key` as the key. Hex digest.
- The `verify_webhook` method must receive `body: bytes`, NOT a parsed dict. The merchant-api's webhook route already calls `await request.body()` BEFORE any Pydantic parsing happens — preserve this contract.

### Webhook contract
- `verify_webhook(headers, body) -> WebhookEvent` is **synchronous**. No I/O. No `async`.
- `verify_transaction(reference: str) -> PaymentStatus` is the async server-side verification. The merchant-api calls them as a two-step pattern (verify locally, then optionally confirm with Paystack).

### Errors
- 401 → `AuthenticationError`
- 404 (transaction not found) → `PaymentNotFoundError`
- 4xx → `InvalidRequestError`
- 5xx / network → `NetworkError`
- Signature mismatch → `SignatureMismatchError`
- Refund failure → `RefundError`
- `httpx.HTTPError` MUST NOT escape the adapter boundary.

### Logging
- `structlog` bound with `provider="paystack"`.
- Never log: `secret_key`, raw signature bytes, full request bodies.
- Log: `reference`, `amount_cents`, `status`, Paystack `id` (their internal transaction id), and event_type.

## Binding quality gates (non-negotiable)

- [ ] Coverage **≥95%** on `providers/paystack.py` — PayFast set 99%, aim for that
- [ ] `mypy --strict packages/lekker-pay/lekker_pay/providers/paystack.py` clean
- [ ] `ruff check` clean
- [ ] `ruff format --check` clean
- [ ] No `Any` types in public method signatures
- [ ] Existing 44 PayFast tests still pass (do not regress)
- [ ] Footgun regression tests by these exact names:
  1. `test_verify_webhook_uses_constant_time_comparison`
  2. `test_money_conversion_integer_cents_no_float_drift`
  3. `test_verify_webhook_uses_raw_bytes_not_parsed_json`
  4. `test_initialize_amount_is_string_refund_amount_is_integer`  ← Paystack-specific
  5. `test_paystack_api_key_used_for_both_bearer_and_webhook_hmac`  ← the duality footgun
  6. `test_abandoned_status_maps_to_failed`  ← Paystack-specific semantic
  7. `test_authorization_url_is_redirect_target_not_access_code`  ← Paystack response-shape footgun

## Workflow

1. **Confirmation** — list the three rationale-doc takeaways and the Paystack-specific footgun analysis (the secret-key duality). Acknowledge the binding Config rule above. **Wait for my acknowledgement.**
2. **Plan** — 5–8 bullet implementation plan covering module structure, which `ProviderConfig` fields you use, test class breakdown, integration touch-points in merchant-api, and open questions. **Wait for my approval.**
3. **Implement adapter** — `providers/paystack.py` first, then `tests/test_paystack.py`. Mock all HTTP I/O with `respx`. Never hit real Paystack endpoints in unit tests.
4. **Self-verify** — run:
   ```
   pytest packages/lekker-pay/tests/test_paystack.py -v --cov=packages/lekker-pay/lekker_pay/providers/paystack.py --cov-report=term-missing
   pytest packages/lekker-pay/tests/test_payfast.py -v   # ensure no regression
   mypy --strict packages/lekker-pay/lekker_pay/providers/paystack.py
   ruff check packages/lekker-pay/
   ruff format --check packages/lekker-pay/
   ```
   Report all results. If anything is below gate, fix it yourself before asking me.
5. **Integrate** — update merchant-api files listed above. Provide me concrete curl/browser steps to verify E2E with the test card.
6. **Recipe update** — propose specific edits to `docs/PROVIDER_RECIPE.md`. Specifically capture: (a) REST flow pattern, (b) raw-body HMAC verification on FastAPI, (c) string/integer amount split when a provider uses different units across endpoints.

## The ambiguity rule (most important)

If Paystack docs are **silent, contradictory, or ambiguous** on ANY of these — STOP and ask me, do not guess:
- Whether ZAR currency requires special account activation (it does on some accounts; flag if your code path assumes it)
- The exact HMAC-SHA512 algorithm input — is it the raw bytes or the body after any normalisation?
- Whether `charge.success` ever fires without a corresponding successful `/transaction/verify` response (idempotency edge case)
- Whether the refund endpoint signs responses the same way as charge webhooks
- What happens to the `reference` field across retries — does Paystack ever change it server-side?

The PayFast empty-passphrase bug cost an hour because a guess was made instead of a question asked. Do not repeat that.

## Definition of done

A real Paystack sandbox payment processed end-to-end:
1. Browser hits `/checkout`, selects "Paystack" in the dropdown
2. Customer is redirected to `checkout.paystack.com/...`
3. Customer pays with `4084 0840 8408 4081`, PIN `0000`, OTP `123456`
4. Webhook arrives at `/webhooks/paystack`, signature verifies
5. Order in Postgres shows `status="paid"`, `webhook_received=true`
6. All tests green, all quality gates met, PayFast tests not regressed
7. Recipe doc updated with new patterns

Begin with the confirmation step. Do not write code until I approve your plan.
