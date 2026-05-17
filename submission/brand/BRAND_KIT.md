# Lekker Pay — Brand Kit v0.1

Hand this to any future designer, agency, or contributor. Everything here is what shipped to the IBM Bob Hackathon submission deck.

**Maintainer:** Delron Claassen · `LimpingXpert` · [Dellie-Yah/lekker-pay-za](https://github.com/Dellie-Yah/lekker-pay-za)

---

## The mark — "L is a railway"

A slate-900 tile carries a white capital L formed by **a station post (vertical) and a rail (horizontal)**. The rail bleeds off the right edge of the tile, signalling that the journey continues past the frame. A single amber-500 dot rests on the rail — a payment in transit, a passenger, a R100 note.

**Geometry (in a 128 × 128 SVG viewport):**

| Element | Position | Size | Fill |
|---|---|---|---|
| Tile | `(0, 0)` | `128 × 128` | `#0F172A` (slate-900) |
| Vertical post | `(32, 32)` | `16 × 64` | `#FFFFFF` |
| Horizontal rail | `(32, 80)` | `96 × 16` | `#FFFFFF` (extends to tile edge) |
| Amber payload | `(88, 72)` r=8 | circle | `#F59E0B` (amber-500) |

**Three variants live in `submission/logo/`:**

| File | What | Use |
|---|---|---|
| `lekka-pay-short-version.svg` | Monogram only — tile + post + rail + dot | Favicon, app icon, social avatar, slide chrome |
| `lekker-pay-variation-b.svg` | Monogram + "Lekker Pay" wordmark (Inter 600) | Standard horizontal lockup — most contexts |
| `lekker-pay-long-version.svg` | Variation B + a slate rail extending to the right margin | Letterhead, close slide, big-format moments |

The deck (`build-deck.js`) doesn't load the SVGs directly — the mark is ported to native pptxgenjs shape primitives in `drawLekkerPayMark()`. Same geometry, no font-import dependency, crisp at every size.

**Inverted variant** for dark backgrounds: white tile, slate-900 post + rail, amber dot stays amber. See `drawLekkerPayMark(slide, x, y, size, { inverted: true })` in `build-deck.js`.

---

## Palette

| Token | Hex | Use |
|---|---|---|
| `slate-900` | `#0F172A` | Primary — tile, headlines, body type |
| `slate-700` | `#334155` | Wordmark sub-text, second-tier copy |
| `slate-500` | `#64748B` | Captions, footers |
| `slate-400` | `#94A3B8` | Mono slide numbers, supporting copy |
| `slate-100` | `#F1F5F9` | Panel fills, soft backgrounds |
| `white`     | `#FFFFFF` | Background, inverted-tile, body text on dark |
| `amber-500` | `#F59E0B` | **Single accent moment per frame** — the L's payload, the one stat that matters |
| `emerald-500` | `#10B981` | Test-pass states ONLY — never decorative |

**Accent rule:** one amber moment per slide, pointing at *the* number that proves the slide. If a slide has no defensible number, it doesn't need amber and probably needs rewriting.

---

## Type pairing

| Slot | Family | Weight |
|---|---|---|
| Display, body | **Inter** | 600 (display headlines), 400 (body), 500 (UI labels) |
| Numbers, code, mono UI | **JetBrains Mono** | 400 (most), 600 (stats), letterSpacing 2–3 on small caps |

Inter via Google Fonts. JetBrains Mono via Google Fonts. Both have generous open-source licences for product, print, web, and ML.

---

## Cover image — "The Flow"

- File: `submission/brand/cover-the-flow.png` (1.2 MB, 16:9)
- Prompt: `submission/brand/cover-the-flow.prompt.txt`
- Concept: dot-density southern Africa silhouette with Madagascar visible, a single amber radiating node, slate-navy network lines emanating from the amber outward in all directions.
- Use: Title slide background (Slide 1), README hero.
- Don't crop the amber node — it's the focal point.

A secondary asset, "The Morning" (warmth-forward overhead desk scene), is available for social cards and blog headers but is not in `brand/` yet — generate from a comparable Midjourney prompt if needed.

---

## Do / don't

| Do | Don't |
|---|---|
| One amber moment per frame | Use amber as decoration |
| Inter + JetBrains Mono, always | Mix in a third typeface |
| Slate-900 tile, white L, amber dot | Recolour the mark or swap the dot for another shape |
| Allow the rail to bleed off the right edge | Pad the rail back inside the tile — kills the "journey continues" reading |
| Use the long-rail variant for moments that earn it (close, letterhead) | Add the long rail everywhere — it loses meaning |
| Hand-built diagrams, monochrome with one amber node | Mermaid diagrams with multi-colour palettes, 3D, gradients, drop shadows |
| White or near-white backgrounds for content slides | Gradient backgrounds, photo backgrounds (except Slide 1 cover image) |
| Photo-realistic warmth ONLY in "Morning"-style hero imagery | Stock photos of handshakes, server racks, world maps |

---

## Voice

| Tone | Example |
|---|---|
| Warm, technical | "ag, that one failed — here's why" (error messages) |
| Specific over abstract | "111 / 111 tests passing" not "well-tested" |
| African specificity | "Cape Town. Joburg. Lagos." — never "emerging markets" |
| No marketing clichés | Never "unlock", "revolutionise", "disrupt", "world-class" |

The brand voice document is `docs/CONCEPT.md` in the main repo. Read it before writing any new marketing copy.

---

## Reproducibility

To regenerate the deck with these brand assets:

```bash
cd submission
npm install
node build-deck.js
powershell -ExecutionPolicy Bypass -File export.ps1
```

The mark is generated as native pptxgenjs shapes (see `drawLekkerPayMark()` in `build-deck.js`) — no external dependencies, no font fetching, deterministic output.

---

*Last updated: 2026-05-17.*
