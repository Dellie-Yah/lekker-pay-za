# Bob Provider Integration Prompt — Universal Template

Copy this prompt verbatim into Bob, filling in the `<<PROVIDER>>` placeholders and the **Provider Facts** section. Everything else is fixed scaffolding earned from the PayFast integration.

---

# Task: Implement the `<<PROVIDER_NAME>>` adapter for Lekker Pay

You are adding a new payment provider adapter to the Lekker Pay library. This is **not isolated code generation** — the adapter must integrate end-to-end through the existing `apps/merchant-api/` so a real sandbox payment can be processed. Treat the contract, the recipe, and the PayFast reference as binding law.

## Read first, in this exact order, before writing any code

1. `packages/lekker-pay/lekker_pay/base.py` — the `BasePaymentAdapter` contract and Pydantic types
2. `packages/lekker-pay/lekker_pay/errors.py` — the exception hierarchy you MUST raise from
3. `packages/lekker-pay/lekker_pay/providers/payfast.py` — the canonical reference adapter (99% coverage)
4. `packages/lekker-pay/tests/test_payfast.py` — the test patterns and footgun regressions
5. `docs/PAYFAST_DESIGN_RATIONALE.md` — the WHY behind every PayFast decision (read in full)
6. `docs/PROVIDER_RECIPE.md` — the procedural checklist and quality gates
7. `docs/providers/<<provider_slug>>.md` — the new provider's API documentation
8. `apps/merchant-api/app/payment_service.py` — the integration surface you will extend
9. `apps/merchant-api/app/config.py` — the env-loading pattern

**Confirmation step:** Before producing any plan or code, list back the three things you consider most important from `PAYFAST_DESIGN_RATIONALE.md` and identify the **equivalent failure mode** for `<<PROVIDER_NAME>>` (e.g. PayFast's empty-passphrase bug → what is the analogous credentials/encoding/ordering trap for this provider?).

## Provider Facts — fill these in from the docs

```
Provider name:           <<PROVIDER_NAME>>
Module slug:             <<provider_slug>>     (lowercase, no spaces)
Flow type:               <<redirect|REST-API|hybrid>>
Auth scheme:             <<Bearer token | HMAC headers | form-encoded signature>>
Signature algorithm:     <<MD5 | HMAC-SHA256 | HMAC-SHA512 | other>>
Signature location:      <<HTTP header X-... | request body field | URL param>>
Signature input:         <<raw bytes | sorted fields | doc-order fields | concatenated query>>
Webhook secret distinct
  from API key?          <<yes|no>>           ← this is a common footgun
Server-side verify API:  <<URL | none>>       ← if present, exposed as separate async method
Currency parameter:      <<required|optional>> Default: ZAR
Amount unit:             <<cents|kobo|rands string>>   Internal stays int cents always
Sandbox base URL:        <<https://...>>
Live base URL:           <<https://...>>
Refund endpoint:         <<URL | not supported>>
Status mapping (provider → PaymentStatus):
  SUCCESS  → SUCCEEDED
  FAILED   → FAILED
  PENDING  → PENDING
  CANCEL   → CANCELLED
  REFUND   → REFUNDED
```

## What you are building (three artefacts)

1. `packages/lekker-pay/lekker_pay/providers/<<provider_slug>>.py` — the adapter
2. `packages/lekker-pay/tests/test_<<provider_slug>>.py` — the test suite
3. Updates to:
   - `packages/lekker-pay/lekker_pay/providers/__init__.py` (export)
   - `packages/lekker-pay/lekker_pay/__init__.py` (top-level export)
   - `apps/merchant-api/app/payment_service.py` (wire-in)
   - `apps/merchant-api/app/config.py` (env vars)
   - `.env.example` (document new env vars, **never** real secrets)
   - `docs/PROVIDER_RECIPE.md` (capture any new patterns you had to invent)

## Hard rules — non-negotiable

### Config
- Use the **generic `ProviderConfig`** from `lekker_pay.base`. Do NOT create a per-provider dataclass or Pydantic model.
- Supply only the fields your provider needs — others stay `None`. (PayFast uses `merchant_id`/`merchant_key`/`passphrase`; Paystack uses `api_key`; etc.)
- No env reads inside the adapter class. Strict constructor injection.
- The adapter's `__init__` validates that the fields it actually needs are present (`if not config.api_key: raise ValueError(...)`).

### Money
- Internally always `int` cents. Never floats. Never strings for arithmetic.
- Conversion to/from wire format uses `Decimal`, never `float`.
- Negative amounts raise `InvalidRequestError`.

### Signatures
- Every signature comparison uses `hmac.compare_digest`. Writing `==` between signature strings is a failure.
- Webhook signature verification reads **raw bytes** from `body`, not Pydantic-parsed JSON.
- Some providers reuse one secret for both API auth AND webhook HMAC (Paystack); others use a distinct webhook secret (Yoco). Either is acceptable — but write a regression test naming the exact behaviour you implemented, so a future contributor can't accidentally flip it.

### Webhook contract
- `verify_webhook(headers, body) -> WebhookEvent` is **synchronous**. No I/O. No `async`.
- If the provider offers server-side verification (e.g. PayFast's `/eng/query/validate`), expose it as a **separate async method**. Never fold it into `verify_webhook`. The merchant-api calls them as a two-step pattern.
- **Idempotency:** `verify_webhook` must be deterministic — the same `body` bytes passed twice must produce equal `WebhookEvent` objects. The merchant-api dedupes via Redis but the adapter cannot rely on that.

### Reference fidelity
- `WebhookEvent.reference` and `PaymentResult.reference` always carry the **merchant-supplied reference** (e.g. `"ORDER-ABC123"`), never the provider's internal numeric `id`.
- The provider's internal id belongs in `provider_payment_id` (stringified) and in `raw`, for debugging only.
- The merchant joins orders by `reference`. Using the provider's id silently breaks order lookup.

### Raw response preservation
- `PaymentResult.raw` and `WebhookEvent.raw` store the **entire** provider response dict. Never filter, never prune to "useful" fields.
- Debugging payments requires the full payload. Selective storage means production incidents take longer to diagnose.

### No defensive config fallbacks
- Use only the `ProviderConfig` fields your provider's documented API requires.
- Do NOT add `config.webhook_secret or config.api_key`-style fallbacks. Silent behaviour change based on which config field is populated is a footgun.
- If the provider later adds a new auth shape, that's a separate change with its own tests — not a hidden fallback.

### Adapter style
- Module-level constants for URLs and other compile-time values. If a `_get_base_url()` "helper" returns the same string in both branches, replace it with a constant. Misleading helpers are worse than no helpers.
- No `Any` types in public signatures. Type the actual shape, even when it's a `dict[str, str | int | bool]` — judges and Bob both read public surfaces.

### Errors
- Every adapter exception inherits from `LekkerPayError`. Map:
  - 401 → `AuthenticationError`
  - 404 → `PaymentNotFoundError`
  - 4xx → `InvalidRequestError`
  - 5xx / network → `NetworkError`
  - Signature mismatch → `SignatureMismatchError`
  - Refund failure → `RefundError`
- Never let `httpx.HTTPError` escape the adapter boundary.

### Logging
- `structlog` bound with `provider="<<provider_slug>>"`.
- Never log: full credentials, passphrases, signatures, raw webhook secrets, full card numbers.
- DO log: reference IDs, amounts, status, correlation IDs.

## Binding quality gates (non-negotiable, recipe-enforced)

- [ ] Coverage **≥95%** on `providers/<<provider_slug>>.py` — PayFast set the bar at 99%, aim for that
- [ ] `mypy --strict packages/lekker-pay/lekker_pay/providers/<<provider_slug>>.py` clean
- [ ] `ruff check` clean
- [ ] `ruff format --check` clean
- [ ] No `Any` types in public method signatures
- [ ] Five **universal** footgun regression tests present and passing by these exact names:
  1. `test_verify_webhook_uses_constant_time_comparison`
  2. `test_money_conversion_integer_only_no_float_drift`
  3. `test_verify_webhook_uses_raw_bytes_not_parsed_json`
  4. `test_webhook_idempotency_same_input_same_output`
  5. `test_reference_uses_merchant_supplied_not_internal_id`
- [ ] At least one **provider-specific** footgun test, named after the failure mode (e.g. `test_empty_passphrase_is_not_appended` for PayFast, `test_<<provider>>_api_key_used_for_both_bearer_and_webhook_hmac` for Paystack)
- [ ] Footgun tests live inside the per-method class where the behaviour is implemented (the idempotency test belongs in `TestVerifyWebhook`, not a separate dumping-ground class). A `TestFootgunRegressions` aggregation class is optional navigation only — these tests must not exist *only* there.

## Workflow

1. **Confirmation** — list the three rationale-doc takeaways and the provider-specific equivalent failure mode. Wait for my acknowledgement.
2. **Plan** — 5–8 bullet implementation plan covering: module structure, which `ProviderConfig` fields you use, test class breakdown, integration touch-points in `merchant-api`, open questions. Wait for my approval.
3. **Implement adapter** — `providers/<<provider_slug>>.py` first, then `tests/test_<<provider_slug>>.py`.
4. **Self-verify** — run `pytest packages/lekker-pay/tests/test_<<provider_slug>>.py -v --cov=lekker_pay/providers/<<provider_slug>>.py --cov-report=term-missing`, then `mypy --strict`, then `ruff check && ruff format --check`. Report results. If anything is below the gate, fix it yourself before asking me.
5. **Integrate** — wire into `apps/merchant-api/app/payment_service.py` and `config.py`. Update `.env.example`. Restart-test instructions for me to verify E2E.
6. **Recipe update** — propose specific edits to `docs/PROVIDER_RECIPE.md` capturing any new pattern this provider forced you to invent. The recipe must evolve.

## The ambiguity rule (this is the most important rule)

If the provider docs are **silent, contradictory, or ambiguous** on any of these — **STOP and ask me**, do not guess:
- Which signature algorithm applies to which endpoint (checkout vs refund vs webhook)
- Whether amount fields are in cents, kobo, or rand decimal strings
- The exact field order or encoding for signature input
- Whether the webhook secret is the API key or a separate value
- What event-type strings the webhook uses
- Whether sandbox and live use the same credentials format

The PayFast empty-passphrase bug cost an hour because a guess was made instead of a question asked. Do not repeat that.

## What "done" looks like

A real sandbox payment processed end-to-end:
1. Browser hits `/checkout`, selects `<<PROVIDER_NAME>>`
2. Redirected to provider sandbox, payment completes
3. Webhook arrives at `/webhooks/<<provider_slug>>`, signature verifies
4. Order in Postgres shows `status="paid"`, `webhook_received=true`
5. All tests green, all quality gates met
6. Recipe doc updated with new patterns

Begin with the confirmation step.
