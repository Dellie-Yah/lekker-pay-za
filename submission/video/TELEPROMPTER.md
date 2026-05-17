# TELEPROMPTER — Lekker Pay submission video

Read aloud. Pause where there's a line break. Breathe at em-dashes.
Total: ~520 words, ~4:30 spoken + demo time = under 5 min.

---

## INTRO — 0:00 to 0:25  (webcam, face only)

Hi judges. I'm Delron Claassen — I go by **LimpingXpert**.

I'm a solo founder in Cape Town.

Over this hackathon I built **Lekker Pay** — an open-source Python library that unifies South Africa's fragmented payment providers behind one API.

Two adapters ship today, both production-grade. **One of them was written by IBM Bob.**

Let me walk you through it.

---

## DECK WALK — 0:25 to 2:00  (slides full-screen)

### Slide 1 — 0:25 to 0:30
Lekker Pay. **One API for South African payments. AI-extensible. MCP-native.**

### Slide 2 — 0:30 to 0:48
South Africa has stations — but no railway.

Sixty-plus regional payment providers — PayFast, Paystack, Ozow, Yoco, Stitch — each with its own auth dance, its own webhook shape, its own midnight footgun.

Just covering the bare minimum burns a merchant **R150,000 to R400,000** in dev fees before they take a single payment.

**Stripe doesn't exist here. Africa needs its own.**

### Slide 5 — 0:48 to 1:18  ← climax, slow down here
This is the **IBM Bob** hook.

The wedge isn't the library — **it's the recipe.**

You give Bob three things: the provider documentation, our reference adapter — PayFast at 98 percent coverage — and a recipe with **eight critical security rules and five universal footgun tests.**

Bob returns a conformant adapter with its full test suite.

Paystack: **683 lines of adapter. 1,002 lines of tests. 92 percent coverage.** One human review pass to widen a JSON type. That's it.

### Slide 8 — 1:18 to 1:35
Five regression tests run against every adapter: constant-time signature comparison, integer-cents money handling, raw-bytes webhook verification, webhook idempotency, merchant-reference fidelity.

**98 percent PayFast. 92 percent Paystack. One-eleven of one-eleven on main.**

### Slide 9 — 1:35 to 1:52
Mastercard puts Africa's digital payments economy at **one-point-five trillion dollars by 2030.**

The orchestration layer is a **200 to 500 million dollar** slice. We target **30 to 80 million ARR by 2031** across SA, Nigeria, Kenya.

**Stripe is worth 159 billion by being the one API. Africa has no one API.**

### Slide 11 — 1:52 to 2:00
Category of one. **Spreedly plus Primer — but Africa-first, and MCP-native.**

---

## DEMO — 2:00 to 4:15  (terminal / browser / VS Code)

### Demo 1 — Tests pass  2:00 to 2:25
First — the tests. Real run, no editing.

*(run `pytest --cov=lekker_pay -q`)*

**One-eleven passing. Ninety-five percent total coverage.** The numbers on the deck are the numbers on main.

### Demo 2 — R100 sandbox payment  2:25 to 3:25
Second — a real R100 sandbox payment.

*(submit the checkout form)*

The merchant API signs the request, opens a Paystack sandbox session, and waits for the webhook.

*(switch to log pane)*

**compare_digest** verified. **Webhook event parsed. Status flips to PAID.** Reference round-tripped. Idempotent on retry.

Real provider sandbox. Real webhook. Real money path.

### Demo 3 — Bob built this  3:25 to 4:15
Third — the methodology.

*(left pane: recipe)*  Here's the recipe. **Eight critical rules**, all enumerated.

*(middle pane: prompt)*  Here's the prompt I gave Bob.

*(right pane: paystack.py)*  And here's what came back. Production-grade Python. Strict-typed. Constant-time crypto. Two-step webhook pattern.

**Bob wrote this. One human review pass. Hours, not weeks. That's the moat.**

---

## CLOSE — 4:15 to 4:45  (webcam, or Slide 14 in background)

That's Lekker Pay.

Open source today — **github.com/Dellie-Yah/lekker-pay-za**.

Hosted platform Q3 2026. MCP server Q4. Marketplace and pan-African expansion Q1 2027.

**Africa has stations. We laid the railway.**

Thanks for watching.

---

## DELIVERY NOTES

- Bold = punch the word. Slight volume lift, then back to normal.
- Em-dashes (—) = breathe.
- Each line break = beat, half a second.
- Don't speed up when you're nervous; **slow down**. The deck is dense — the audience needs you to pace it.
- If you fluff a line, just continue. You'll edit it out in post.
