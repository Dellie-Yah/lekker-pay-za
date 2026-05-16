# PayFast Adapter — Design Rationale

> **For Bob and contributors.** This document explains *why* `payfast.py` is
> written the way it is. The code captures the *what*; this captures the
> reasoning so Bob can generalize the patterns when generating Ozow, Yoco,
> and beyond. Read this in full before generating any new adapter.

---

## 1. Why PayFast is hand-written, not Bob-generated

PayFast is the **reference adapter**. Every other adapter Bob produces will
pattern-match against this file. If PayFast is sloppy, every downstream
adapter is sloppy. The investment in writing this by hand is amortised
across every future provider.

Bob does not write PayFast. Bob *reads* PayFast.

---

## 2. The signature field order trap

The single most common PayFast integration bug — present in countless open
GitHub issues — is sorting fields alphabetically before signing. **PayFast's
checkout signature uses documentation order, not alphabetical order.**

The order is documented in PayFast's "Create your checkout form" page (Step
2, signature section). It groups fields semantically:

1. Merchant Details: `merchant_id`, `merchant_key`, `return_url`,
   `cancel_url`, `notify_url`
2. Buyer Detail: `name_first`, `name_last`, `email_address`, `cell_number`
3. Transaction Details: `m_payment_id`, `amount`, `item_name`,
   `item_description`, `custom_int1..5`, `custom_str1..5`
4. Transaction Options: `email_confirmation`, `confirmation_address`
5. Payment Method: `payment_method`
6. Recurring Billing: `subscription_type`, `billing_date`,
   `recurring_amount`, `frequency`, `cycles`

This order is encoded in `_CHECKOUT_SIGNATURE_FIELD_ORDER` and tested
explicitly in `test_field_order_is_documentation_order_not_alphabetical`.

**Generalisation for Bob:** every provider has a signature-field-order spec
buried in their docs. Read it carefully. Encode it as a module-level
constant. Add an explicit test that asserts alphabetical sort produces a
*different* signature, locking in the divergence.

---

## 3. The empty passphrase trap

In November 2025, a public production post-mortem documented 100% payment
failure caused by appending an *empty* passphrase to the signature string.
PayFast accepts merchants who disable the passphrase entirely in
production — and when they do, the passphrase clause must be omitted from
the signature input, not included as `&passphrase=`.

Our implementation:

```python
if passphrase:
    payload += "&passphrase=" + urllib.parse.quote_plus(passphrase.strip())
```

The truthy check is intentional. `passphrase=""` falls through.

This is regression-tested in `test_empty_passphrase_NOT_appended`. The test
exists not to prove the code works today, but to **prevent regeneration
from reintroducing the bug**.

**Generalisation for Bob:** any time a provider has an "optional secret"
appended to signature input, add an explicit test that the empty case
produces the secret-less hash. Optional fields are where signature schemes
silently break.

---

## 4. URL encoding — quote_plus, not quote, and don't post-process

PayFast's *own published* Python example contains a bug:

```python
# DON'T do this — it's the PayFast docs example
encoded = urllib.parse.quote_plus(value).replace("+", " ")
```

`quote_plus` already correctly turns spaces into `+`. Calling
`.replace("+", " ")` reverses that, breaking the signature for any value
containing a space. We do not copy this.

```python
# What we do
encoded = urllib.parse.quote_plus(value.strip())
```

Regression-tested in `test_url_encoding_uses_plus_for_space`.

**Generalisation for Bob:** when a provider's documentation includes
sample code, treat it as untrusted input. Verify behavior against actual
provider responses, not the docs' Python example.

---

## 5. Money handling — integer cents in, formatted strings out

Floats and money are a never-event. Floats drift; signatures break;
auditors get angry.

Internal representation: `int` cents (e.g. `R150.00` → `15000`).

External representation: whatever the provider expects, formatted via
`Decimal`. For PayFast checkout, this is a 2-decimal rand string:

```python
rands = Decimal(cents) / Decimal(100)
return f"{rands:.2f}"  # "150.00"
```

Note: the PayFast **Refunds API** uses cents directly — no formatting — and
this is documented in the refund() method. The inconsistency between the
two PayFast surfaces is a real footgun; it's tested in the refunds test
class.

**Generalisation for Bob:** every adapter has a `_cents_to_provider_format`
helper. Test it with `0`, `1`, `8550` (the float-drift case), and negative
values. Never reach for `float` even briefly.

---

## 6. The ITN signature is in the body, not in headers

This is a PayFast quirk. Almost every other modern payment webhook puts
the signature in an HTTP header (`Webhook-Signature`, `X-Signature`, etc).
PayFast embeds it as a form field in the POST body, alongside the other
fields it's signing over.

This means our `verify_webhook` implementation:

1. Parses the form-encoded body
2. Pops the `signature` field out
3. Computes the expected signature from what remains
4. Constant-time compares

The `headers` parameter is unused for PayFast and `del`'d explicitly to
silence linters. It's still part of the method signature because the
[`BasePaymentAdapter`](../lekker-pay/lekker_pay/base.py:160) contract requires it — Yoco and others do use
headers.

**Generalisation for Bob:** check where the signature lives *before*
generating verification code. Document this in the per-provider doc. Yoco
puts it in `Webhook-Signature` header. Ozow puts it in the body like
PayFast. Stripe puts it in `Stripe-Signature`. Etc.

---

## 7. Three-layer ITN security

PayFast's official security guidance for ITN handlers (from `payfast.io`):

1. **Verify the signature** — that the payload wasn't tampered with.
2. **Verify the source IP** — that it belongs to PayFast.
3. **Verify the amount** — that the gross paid matches the order amount.
4. **Server-to-server validation** — POST the ITN body back to
   `/eng/query/validate` and confirm the response is the literal text
   `VALID`.

Our adapter implements layers 1 and 4. Layers 2 and 3 belong to the
merchant application code (`apps/merchant-api/`), not to the adapter,
because:

- **IP whitelisting** depends on infrastructure (reverse proxies,
  `X-Forwarded-For` parsing) the adapter can't see, and PayFast migrated
  to AWS in July 2025 so the IP set is no longer stable.
- **Amount verification** requires knowledge of the merchant's order
  table, which the adapter does not have.

The adapter's job is to make the data *trustworthy enough to act on*.
What the merchant does with that trust — including amount-matching against
their own order DB — is up to the merchant.

**Generalisation for Bob:** keep the adapter's surface narrow. Signature
verification is the adapter's job. Source IP, amount matching, and
idempotency are the merchant application's job. Don't bleed concerns.

---

## 8. `verify_webhook` is synchronous

Webhook signature verification is pure CPU work (HMAC, MD5, byte
comparison). There is no I/O. Making it `async` would force every caller
to `await` for no reason and add an event loop hop per webhook.

The `validate_itn` follow-up call *is* async because it does I/O.

**Generalisation for Bob:** make sync things sync. The `async` keyword is
not a quality signal; it's an I/O signal.

---

## 9. Constant-time signature comparison

```python
if not hmac.compare_digest(received_signature, expected_signature):
    raise SignatureMismatchError(...)
```

Standard `==` comparison short-circuits on the first mismatching character.
A determined attacker can measure response time to recover a valid
signature byte-by-byte (timing attack). [`hmac.compare_digest()`](https://docs.python.org/3/library/hmac.html#hmac.compare_digest) runs in
constant time regardless of input.

This applies *anywhere* signatures or secrets are compared, not just here.

**Generalisation for Bob:** any string compare involving secret-derived
material uses [`hmac.compare_digest()`](https://docs.python.org/3/library/hmac.html#hmac.compare_digest). Add a recipe-doc rule: if Bob writes
`==` near a signature field, the recipe is incomplete.

---

## 10. The Refunds API is a different beast

PayFast's checkout flow and PayFast's Refunds API share a brand name and
nothing else:

| | Checkout | Refunds |
|---|---|---|
| Endpoint | `payfast.co.za/eng/process` | `api.payfast.co.za/refunds` |
| Auth | Form fields | HTTP headers |
| Sig fields | Body params | Headers + body |
| Sig order | Documentation order | Alphabetical |
| Body format | Form-encoded | JSON |
| Amount format | Rand string `"150.00"` | Cents integer `15000` |
| Sandbox | Different host | Same host + `?testing=true` |

The two should not be unified or DRY'd up. They are genuinely separate
surfaces. The shared MD5+passphrase pattern is coincidence.

**Generalisation for Bob:** providers often have multiple APIs with
divergent conventions. When implementing a new method on the adapter,
re-read the *specific* API docs for that method. Do not assume the
provider's auth/signing scheme is uniform across endpoints.

---

## 11. Idempotency lives outside the adapter

PayFast's ITN can fire more than once for the same `pf_payment_id`
(retries, manual re-delivery, network burps). The adapter does *not* try
to prevent duplicate processing — it would have to maintain state, which
breaks the stateless rule.

Instead, the merchant-api layer keeps a Redis set of
`processed:{provider}:{provider_payment_id}` keys with a 24-hour TTL and
short-circuits the order-update if it's already there.

**Generalisation for Bob:** if a piece of logic requires persistent state,
it does not belong in the adapter. The adapter is a pure transformation
between provider wire format and our unified types.

---

## 12. Testing patterns

Each public method has at least:

- One happy-path test (it works for valid input)
- One failure-path test (it raises the right error for wrong input)

Each *known footgun* has a dedicated regression test (signature field
order, empty passphrase, URL encoding plus-for-space, refunds vs checkout
signature divergence). These tests exist primarily so that Bob, when
regenerating this file, cannot regress them silently.

HTTP I/O is mocked with `respx` against the real URLs the adapter would
hit. We never make real network calls in unit tests.

**Generalisation for Bob:** for every per-provider quirk encoded in the
recipe doc, write a corresponding regression test. The test is the
machine-readable form of the recipe rule.

---

## 13. What this file does NOT do

- **No retries.** httpx has a single attempt. Retry policy belongs in the
  caller — different operations warrant different retry semantics
  (idempotent get_status retries differently to non-idempotent refund).
- **No logging of sensitive data.** Passphrase, signatures, full
  credentials never appear in log lines. Reference IDs and amounts do.
- **No rate-limiting awareness.** PayFast has soft limits; a future
  iteration could surface 429 → `RateLimitError`, but PayFast does not
  emit standard `Retry-After` so this is left for later.
- **No subscription / recurring billing logic.** PayFast supports these
  through the same checkout signature with additional fields. v1 is
  one-time payments. Recurring is a v0.2 milestone.

---

## TL;DR for Bob

When you generate a new adapter:

1. Find and encode the **field order** for the provider's signature as a
   module-level constant. Add a test that alphabetical order produces a
   *different* hash.
2. Handle the **optional-secret** case (`if passphrase: ...`). Test it.
3. Use **`quote_plus`** for URL encoding. Never post-process.
4. Money is **int cents internal, formatted externally**. Decimal for
   conversion, never float. Test with `8550` to lock out float drift.
5. Find the **signature location** (header vs body field). Document it in
   the per-provider doc.
6. Use **[`hmac.compare_digest()`](https://docs.python.org/3/library/hmac.html#hmac.compare_digest)** for every signature compare.
7. [`verify_webhook()`](../lekker-pay/lekker_pay/base.py:245) is **sync**. Use async only where I/O actually
   happens.
8. Adapter is **stateless**. Constructor config. No env reads. No DB.
9. Every adapter method: full type hints, docstring with example,
   happy-path test, failure-path test.
10. Read the *specific* docs for *every* method. Provider APIs are not
    internally consistent — see PayFast checkout vs refunds.

---

## Implementation Checklist

Before implementing any new adapter, verify:

- [ ] Signature field order documented and tested
- [ ] Optional secret handling tested (empty case)
- [ ] URL encoding uses `quote_plus` without post-processing
- [ ] Money conversion helper with test cases (0, 1, 8550, negative)
- [ ] Signature location documented (header vs body)
- [ ] All signature comparisons use [`hmac.compare_digest()`](https://docs.python.org/3/library/hmac.html#hmac.compare_digest)
- [ ] [`verify_webhook()`](../lekker-pay/lekker_pay/base.py:245) is synchronous
- [ ] Adapter is stateless (config via constructor)
- [ ] Full type hints on all methods
- [ ] Docstrings with examples
- [ ] Happy-path and failure-path tests
- [ ] Provider-specific quirks documented and tested

---

## Related Documentation

- [Base Payment Adapter](../lekker-pay/lekker_pay/base.py) - Abstract interface
- [Error Hierarchy](../lekker-pay/lekker_pay/errors.py) - Exception types
- [PayFast Provider Docs](payfast.md) - PayFast-specific details
- [Architecture](../ARCHITECTURE.md) - System design
- [Development Guide](../DEVELOPMENT.md) - Setup and workflow

---

*This document is the source of truth for adapter implementation patterns.
When in doubt, refer back to these principles.*