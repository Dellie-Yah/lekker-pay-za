# Demo command sheet — keep this open in a side window during recording

Every command you'll need, in execution order. Pre-stage everything in Section 0 before pressing record.

---

## SECTION 0 — Pre-recording stage (do this 5 min before camera rolls)

Open three terminal windows side-by-side:

### Terminal A — Stack (already running, monitoring)

```bash
cd "D:/DELRON/CODING PROJECTS/IbmBobHackathon"
docker compose up -d
docker compose logs -f merchant-api | grep -E 'webhook|checkout|PAID|compare_digest'
```

Leave this streaming logs. You'll switch focus to it during Demo 2.

### Terminal B — Tunnel (for the webhook to reach you)

```bash
cloudflared tunnel --url http://localhost:8000
```

**Copy the public URL it prints** (e.g. `https://random-words-1234.trycloudflare.com`). Then in another shell:

```bash
export WEBHOOK_BASE_URL="https://random-words-1234.trycloudflare.com"
docker compose restart merchant-api
```

### Terminal C — pytest target (clean shell for Demo 1)

```bash
cd "D:/DELRON/CODING PROJECTS/IbmBobHackathon/packages/lekker-pay"
clear
```

Leave the cursor at a blank prompt — this is what the camera will see when Demo 1 starts.

### Browser

- **Tab 1:** `http://localhost:8000` (the merchant checkout form — pre-loaded but not filled)
- **Tab 2:** Paystack sandbox dashboard (logged in, ready to receive)
- **Tab 3:** `http://localhost:8000/orders/REFERENCE_PLACEHOLDER` (replace after checkout)

### VS Code

Open these three files in a vertical-split layout (Cmd/Ctrl+\ twice):

| Pane | File | Scroll to |
|---|---|---|
| Left | `docs/PROVIDER_RECIPE.md` | The `## Critical Security Rules` heading — show all 8 `### N. Name` subsections |
| Middle | `docs/BOB_PAYSTACK_PROMPT.md` | Top of file |
| Right | `packages/lekker-pay/lekker_pay/providers/paystack.py` | The `verify_webhook` function |

---

## SECTION 1 — Demo 1: Tests pass (2:00 → 2:25, 25 sec)

**Focus:** Terminal C (clean shell at `packages/lekker-pay`).

```bash
python -m pytest --cov=lekker_pay -q
```

What to point at on camera:
- The dots (each `.` is a passing test — 111 of them stream by)
- The bottom block: `111 passed`, `Total coverage: 95.36%`, `Required test coverage of 85.0% reached.`

If pytest is slow on first run, run it once during Section 0 to warm caches, then `clear` before the take so the real one is fast.

---

## SECTION 2 — Demo 2: Real R100 payment (2:25 → 3:25, 60 sec)

**Focus:** Browser tab 1 (the checkout form), then Terminal A (logs), then Browser tab 3 (order status).

### Step-by-step on camera

1. **Switch to browser tab 1** (`localhost:8000`). The form is already loaded.
2. **Fill the form** while you narrate. Pre-decide these values so you don't fumble:
   - Amount: `10000` (= R100.00)
   - Email: `test@lekkerpay.dev`
   - Name: `Demo Reviewer`
   - Provider: select `paystack` from the dropdown
3. **Click "Create Payment".** The page redirects to the Paystack sandbox.
4. **In the Paystack sandbox**, use the test card:
   - Card: `4084 0840 8408 4081`
   - CVV: `408`
   - Expiry: `12/30`
   - PIN: `0000`
   - OTP: `123456`
5. **Watch the redirect back** to `localhost:8000/orders/ORDER-XXXX?status=success`.
6. **Switch focus to Terminal A.** Point at the streaming log lines:
   - `checkout_request_received amount_cents=10000`
   - `webhook_received provider=paystack`
   - `compare_digest verified`
   - `WebhookEvent status=PAID`
7. **Hit refresh on the order page** — status shows `PAID`.

### Alternative — pure curl (if you don't want the browser dance on camera)

```bash
curl -s -X POST http://localhost:8000/checkout \
  -H "Content-Type: application/json" \
  -d '{"amount_cents":10000,"customer_email":"demo@lekkerpay.dev","customer_name":"Demo Reviewer","provider":"paystack"}' \
  | python -m json.tool
```

Copy the `redirect_url` from the JSON response, open it in a browser to complete the test card flow, then:

```bash
curl -s http://localhost:8000/orders/ORDER-XXXXXXXXXXXX | python -m json.tool
```

…to show the order flipped to `"status": "PAID"`.

---

## SECTION 3 — Demo 3: Bob built this (3:25 → 4:15, 50 sec)

**Focus:** VS Code three-pane layout. You're narrating over three already-open files. No commands to run.

1. **Scroll the left pane** through `PROVIDER_RECIPE.md §Critical Security Rules`. Pause briefly on the eight numbered headings. Say "eight critical rules" and let the headings scroll.
2. **Switch focus to middle pane** (`BOB_PAYSTACK_PROMPT.md`). Show the top — "this is the literal prompt I gave Bob."
3. **Switch focus to right pane** (`paystack.py`). Scroll to `verify_webhook` — the function with the `hmac.compare_digest` call and the raw-bytes handling. Pause for 3 seconds so judges can see real Python with real security primitives.
4. **Close beat:** "Bob wrote this. One human review pass. Hours, not weeks."

---

## TROUBLESHOOTING (in priority order)

| Symptom | Fix |
|---|---|
| `pytest` says coverage fail | Make sure you're in `packages/lekker-pay` not the repo root. |
| Webhook never arrives | Check `cloudflared` tunnel is still up. Free tunnels die after ~2 hours. |
| Paystack sandbox card declined | Use card `4084 0840 8408 4081` exactly. |
| `compare_digest` failing in log | Check `PAYSTACK_SECRET_KEY` matches your Paystack sandbox integration. |
| `Order not found` on the orders page | Use the path without the query string for the API call. |

---

## ONE-LINER ANSWER IF A JUDGE QUESTIONS YOU LATER

> *"Every number in the deck is in the repo. `git clone github.com/Dellie-Yah/lekker-pay-za && cd packages/lekker-pay && pytest --cov=lekker_pay`. The 98% PayFast, 92% Paystack, 111-of-111 — those are the actual numbers."*
