# Lekker Pay — Hackathon Submission Video Script

**Format:** MP4 · 1080p · 16:9
**Length:** 4 minutes 45 seconds (15-second buffer under the 5-min cap)
**Structure:** Intro (25s) · Deck walk (95s) · Live demo (135s) · Close (30s)

For the actual lines to speak, see `TELEPROMPTER.md`. This file is the *direction* — scenes, transitions, recording plan, post-production notes.

---

## TOOLS YOU NEED (free, ~20 min to install if missing)

1. **OBS Studio** — screen + webcam recording. https://obsproject.com
   - Output: MP4, 1920×1080, 30 fps, AAC audio 192 kbps
   - Scenes to set up: `webcam-only` · `slides-only` · `slides + webcam-corner` · `terminal-fullscreen` · `vscode-3pane`
2. **Microsoft Clipchamp** — already on Windows 11. Use it to trim and stitch the takes. (Or Camtasia / DaVinci Resolve if you have them.)
3. **Mic:** anything decent. AirPods are fine if you can't avoid them; a desk mic is better.

## PRE-RECORDING CHECKLIST (5 minutes)

- [ ] Close Slack, Discord, browser notifications, taskbar pop-ups
- [ ] Hide desktop icons (right-click → View → Hide desktop icons)
- [ ] Set Windows to Do Not Disturb
- [ ] Pre-stage the demo: start the merchant-api + open the three VS Code panels (see `DEMO_COMMANDS.md`)
- [ ] Open the PDF: `submission/lekker-pay-submission.pdf` in PowerPoint slideshow mode (F5) so slide cuts are clean
- [ ] Run a 30-second mic test in OBS — listen back, no clicks, no hum
- [ ] Drink water. The voice carries better.

---

## RECORDING ORDER (multi-take recommended)

Record each scene separately, in this order:

1. **Scene 3 (live demo)** first — it's the riskiest, do it while you're fresh
2. **Scene 2 (deck walk)** — easy, you just narrate over slides
3. **Scenes 1 and 4 (intro + close)** — webcam, do these last so you've warmed up

Stitch in Clipchamp. Total recording time: about 45–60 minutes including a couple of retakes. Editing: 15–30 minutes. **Realistic budget: 90 minutes from "record" to "final MP4".**

---

## POST-PRODUCTION (15 min in Clipchamp)

1. **Trim** the silence at the start and end of every take.
2. **Stitch** the 4 scenes in order. No fancy transitions — straight cuts are professional.
3. **Captions** — Clipchamp auto-generates them. Pass once to fix "Lekker" (it'll spell it "Lecker" or "Liquor"), "PayFast", "Paystack", "MCP", "Sigstore".
4. **Levels** — normalise audio to about -16 LUFS. Clipchamp has a one-click loudness fixer.
5. **Export** — MP4, 1080p, 30fps, ~8 Mbps video bitrate. File should land at 250–350 MB.

## NICE-TO-HAVES (skip if short on time)

- **Lower-thirds:** When you say "Delron Claassen — LimpingXpert", flash your name + handle as a text overlay for 3 seconds. Adds 5 minutes of editing for material polish gain.
- **Background music:** Soft, instrumental, no lyrics. Volume at about -28 dB so it doesn't fight the voice. YouTube Audio Library has free options. **Skip if it adds stress** — a clean voice recording is better than a hurried score.
- **Branded outro card:** Last 3 seconds, full-bleed slate-900 with the L tile + "github.com/Dellie-Yah/lekker-pay-za". Slide 14 of the deck IS this card — use it.

## COMMON FAILURE MODES (avoid)

| Mistake | Fix |
|---|---|
| Reading the script flat | Two practice runs first. Mark where to breathe. |
| Demo errors on camera | Pre-stage everything. Run the full demo silently once before the take. |
| Going over 5 minutes | Cut Slide 11 (category) and tighten Demo 2 to 45s if you're over at 3:30. |
| Webcam dark / grainy | Sit facing your window, not away from it. Natural light beats any USB webcam. |
| Mic clipping / sibilance | Test 30 seconds in OBS. If "Lekker" and "Paystack" hiss, move the mic 6cm further away. |
