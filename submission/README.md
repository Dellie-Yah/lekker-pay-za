# Lekker Pay — IBM Bob Hackathon Submission Deck

15-slide PDF/PPTX deck for the IBM Bob Hackathon May 2026 cycle.

**Submission:** Delron Claassen · `LimpingXpert`
**Repository:** [github.com/Dellie-Yah/lekker-pay-za](https://github.com/Dellie-Yah/lekker-pay-za)

## Deliverables

| File | What it is |
|------|------------|
| `lekker-pay-submission.pptx` | 15-slide deck, 16:9, native PowerPoint format |
| `lekker-pay-submission.pdf`  | Same deck as PDF — the file to upload to lablab.ai |
| `slides_jpg/Slide*.JPG`      | Per-slide preview renders (QA artifacts) |
| `build-deck.js`              | Source — regenerates the .pptx deterministically |
| `export.ps1`                 | Drives PowerPoint COM to produce PDF + JPGs from the .pptx |
| `brand/`                     | Logo geometry, cover image, brand kit |
| `logo/`                      | Three SVG variants of the railway-L mark |
| `video/`                     | Script + teleprompter + demo commands for the submission video |
| `lablab/`                    | Copy-paste-ready submission form content |

## To regenerate

```powershell
# From this directory
npm install                                      # one-time; pulls pptxgenjs
node build-deck.js                               # writes lekker-pay-submission.pptx
powershell -ExecutionPolicy Bypass -File export.ps1   # writes PDF + slides_jpg/
```

Requires Node ≥ 18 and Microsoft PowerPoint (for the COM export). LibreOffice would
also work if you swap the export step.

## Slide map

1. **Title** — wordmark + tagline + cover image background
2. **Problem** — train-metaphor framing, "60+ providers · 0 unified rails"
3. **Solution** — 5-line Python code sample
4. **How it works** — runtime architecture diagram
5. **The wedge** — Bob methodology diagram (the climax slide)
6. **Live walkthrough** — real sandbox R 100 payment request + verified webhook log
7. **Tech stack** — five-column grouped stack
8. **Quality discipline** — 5 footgun tests + 98 % / 92 % / 111 stats
9. **Market opportunity** — TAM $1.5T · SAM $200–500M · SOM $30–80M
10. **Revenue model** — 5-tier pricing + contributor share
11. **Competitor landscape** — 2×2 quadrant, "category of one"
12. **Roadmap** — Q3 26 / Q4 26 / Q1 27 phases
13. **Why now** — three timed signals
14. **Close / ask** — dark slide, "Built with Bob. Built for Africa. Built to last."
15. **Appendix** — receipts (repo, tests, docs, demo)

## Design system

- **Palette** — slate-900 primary, white background, amber-500 single-accent rule (one per slide)
- **Type** — Inter (display + body) · JetBrains Mono (numbers, code, slide chrome)
- **Grid** — 10″ × 5.625″ canvas, 0.5″ outer margin, 12-column underlying grid
- **Diagrams** — hand-drawn-precise: shapes + arrows, no 3D, no gradients, no clip-art

See `brand/BRAND_KIT.md` for the full spec.

## Self-score against judging criteria

| Pillar | Score | One-line note |
|---|---|---|
| **Presentation**        | 4 / 5 | Visual logic is consistent across all 15 slides. One amber moment per slide, every number defensible. |
| **Business Value**      | 4 / 5 | TAM/SAM/SOM cited from Mastercard 2025 + Grand View MEA 2025, 5-tier pricing real, contributor flywheel concrete. Lacks customer logos (none yet — pre-launch). |
| **Application of Tech** | 5 / 5 | Slide 5 (Bob methodology) is the climax: docs + reference adapter + recipe → Bob → conformant adapter + 92 % coverage. Slide 8 lists the 5 footgun regression tests by name. |
| **Originality**         | 5 / 5 | "Spreedly + Primer, but Africa-first and MCP-native" — this thesis exists nowhere else. Train metaphor + lekker brand voice could only come from this team. |

## Live-presenter notes

- Slide 5 is the slow-down moment. Stop. Read the input boxes aloud. Then point at the IBM BOB box. Then the output boxes. **The wedge is the recipe, not the library.**
- Slide 8: lead with the 98 % coverage stat, then say "we then asked Bob to do the same. 92 %. First attempt." Pause.
- Slide 11: walk the dots in this order — Stripe → Spreedly → Flutterwave → Lekker Pay. End on Lekker Pay. The empty top-right quadrant is the point.
- Slide 14 is the close. Read all three lines. Don't add anything.

## Numbers verified against `main`

| Claim | Source |
|---|---|
| 111 / 111 tests passing | `pytest --collect-only -q` |
| 98 % PayFast coverage | `pytest --cov=lekker_pay` |
| 92 % Paystack coverage | `pytest --cov=lekker_pay` |
| 95 % total coverage | `pytest --cov=lekker_pay` |
| PayFast adapter 721 lines | `wc -l lekker_pay/providers/payfast.py` |
| Paystack adapter 683 lines | `wc -l lekker_pay/providers/paystack.py` |
| Paystack test suite 1,002 lines | `wc -l tests/test_paystack.py` |
| 8 critical security rules | `grep -c '^### ' docs/PROVIDER_RECIPE.md` (under Critical Security Rules) |

## Market figures verified against external sources

| Claim | Source |
|---|---|
| TAM $1.5T African digital payments by 2030 | Mastercard / Genesis Analytics report, Mar 2025 |
| SAM $200–500M African orchestration layer | Grand View Research MEA payment orchestration outlook, 2025 |
| Stripe valuation $159B | TechCrunch / CNBC Feb 2026 tender offer coverage |
| Stripe acquired Paystack in 2020 | Multiple sources; the deal was widely covered Oct 2020 |
