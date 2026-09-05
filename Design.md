# Design System: IntentGuard

Authorization control room for agent payments. The UI should feel like a precision instrument that decides whether money may move — not a consumer chatbot and not a glowing "AI" marketing site.

**Density:** Daily-app balanced, tightening to cockpit on the Decision and Audit screens (metadata, amounts, timestamps in mono).  
**Variance:** Offset / asymmetric session layout — not a centered SaaS hero.  
**Motion:** Fluid, restrained spring physics. Status changes interpolate; verdicts do not bounce like a game.

---

## 1. Visual theme and atmosphere

Dark zinc substrate, cool and dry. Surfaces are machined panels (nested shells, hairline separators), not floating pastel cards. Typography does the hierarchy: Geist for language, Geist Mono for money, scores, IDs, and timestamps.

The product’s emotional job is **trust through inspectability**. Every screen should make the contract, the proposal, and the verdict comparable at a glance. Blocked states are calm and final, not theatrical. Approved states are quiet — approval is earned, not celebrated with confetti.

Single brand accent: **Signal Teal**, used for primary actions (Compile, Confirm intent, Confirm pause). Verdict colors are **semantic status tokens**, not extra brand accents.

---

## 2. Color palette and roles

Neutrals stay cool. Do not mix warm gray.

- **Void Canvas** (`#101114`) — App background. Not `#000000`.
- **Panel Steel** (`#18191E`) — Inner surfaces, decision well, timeline rail field.
- **Raised Iron** (`#1F2026`) — Nested inner cores, inputs, code/contract blocks.
- **Hairline** (`rgba(255,255,255,0.08)`) — 1px structural borders only. No 1px solid gray-on-gray mush.
- **Primary Ink** (`#E8E9ED`) — Headlines, verdict labels, contract field names.
- **Muted Telemetry** (`#8B8E99`) — Helper text, secondary labels, inactive steps.
- **Faint Meta** (`#5C5F6A`) — Timestamps, hashes truncated, policy version.

**Brand accent (one):**

- **Signal Teal** (`#3F8F7A`) — Primary buttons, focus rings, active step marker, confirmed-intent check. Saturation kept under 80%. No teal outer glow.

**Semantic status (verdicts and engine rows only):**

- **Verdict Approve** (`#4A9B73`) — Hard-pass ticks, APPROVED stamp. Desaturated.
- **Verdict Pause** (`#C4A15A`) — PAUSED, review required. Gold, not warning-orange neon.
- **Verdict Block** (`#C45C4A`) — BLOCKED, constraint fail, payment not initiated. Rose, not `#FF0000`.
- **Risk Low** — use Muted Telemetry or Approve at low opacity.
- **Risk High** — Verdict Block text, no bloom shadow.

Do not use purple, violet, electric neon blue, or gradient-filled headlines.

---

## 3. Typography rules

Dashboard pairing only. No serif.

- **Display / UI:** [Geist](https://vercel.com/font) — tracking tight (`-0.04em` headlines, `-0.02em` titles). Weight-driven hierarchy. Headlines are large but controlled (`clamp(1.75rem, 3vw, 2.75rem)`), not viewport-screaming.
- **Body:** Geist, `1rem`, leading `1.55`, max `65ch` for explanatory copy (reasons, pause questions).
- **Telemetry:** Geist Mono — **all amounts, percentages, intent IDs, SKUs, timestamps, hashes, semantic scores**. Tabular lining figures. Tracking `0.04em` on small caps labels (`HARD CONSTRAINTS`, `SEMANTIC MATCH`).
- **Micro labels:** Geist Medium, `10px`–`11px`, uppercase, `letter-spacing: 0.18em` for section eyebrows (`INTENT CONTRACT`, `PROPOSED TRANSACTION`).

**Banned:** Inter, Roboto, Open Sans, Arial, Helvetica, generic Georgia/Times on this product.

Numbers on Decision and Audit screens are always mono.

---

## 4. Layout principles

- Session chrome: left-aligned product mark + intent id (mono) ; right: step indicators (Create / Run / Decision / Audit). Not a sticky full-bleed marketing nav glued to the top. A floating **compact island** under the top edge (`mt-4`, centered horizontally but content inside is split, `w-[min(1120px,calc(100%-2rem))]`, `rounded-full` shell).
- Page body: `max-w-[1400px] mx-auto`, horizontal padding `px-4 md:px-8`.
- **Create Intent:** split — left prompt and textarea (`~ 7/12`), right live contract preview (`~ 5/12`). On `<768px`, stack: prompt then contract.
- **Run:** activity list full width, proposed-action panel docks to the right on desktop (`2fr / 1fr`).
- **Decision (hero):** asymmetric. Left: amount (macro mono numeral) + product name. Right: stacked check rows (hard, semantic, risk) then a large verdict stamp. Not three equal cards in a row.
- **Audit:** vertical spine, events as rows with time in mono on the left rail, not a card grid.
- Full-height shells use `min-h-[100dvh]`, never `h-screen`.
- CSS Grid for structure. No `w-[calc(33%-1rem)]` flex math.
- Below `768px`: single column, `w-full`, no horizontal scroll, tap targets ≥ `44px`.
- Visible compartmentalization via hairlines and nested bezels, not heavy drop shadows.

**Double-bezel (required on contract panel, decision well, proposal panel):**

- Outer: `p-1.5`, `rounded-[1.75rem]`, `bg-white/5`, hairline ring.
- Inner: `rounded-[calc(1.75rem-0.375rem)]`, Panel Steel, inset highlight `shadow-[inset_0_1px_0_rgba(255,255,255,0.08)]`.

Do not use generic `rounded-xl` cards with `shadow-md`.

---

## 5. Component stylings

### Buttons

- Primary: Signal Teal fill, ink-on-teal or near-white label, `rounded-full`, `px-6 py-3`. Trailing icon sits in its own circle (`w-8 h-8 rounded-full bg-black/20`).
- Secondary: transparent, hairline, Primary Ink.
- Destructive / reject pause: hairline + Verdict Block text, not a huge red fill.
- Active: `scale-[0.98]`. Hover: no neon glow; slight inner brightness.
- Disabled: opacity and no pointer — used when compile is invalid.

### Inputs

- Label above, helper under label or below field, error below in Verdict Block.
- `gap-2` within a field block.
- Background Raised Iron, hairline, focus ring Signal Teal `2px` offset, no floating labels.
- Intent textarea: min-height ~ `10rem`, Geist, placeholder in Muted Telemetry. Example placeholder is a real task, not "Type something magical…".

### Contract preview

- Two groups: **Hard constraints** and **Preferences**.
- Key in Muted Telemetry uppercase micro; value in Geist Mono for numbers, Geist for phrases.
- Draft vs Active: eyebrow badge (`DRAFT` muted, `ACTIVE` teal).

### Decision rows

- Each check is a horizontal row: label | status glyph | value.
- Hard: pass/fail, not a percentage.
- Semantic: percentage in mono (`61%`) plus one-sentence reason.
- Risk: `LOW | MEDIUM | HIGH`.
- Verdict: single word `APPROVED` / `PAUSED` / `BLOCKED` in display weight, colored with the matching status token. Optional thin stamp/outline, no emoji.

### Agent activity

- Ordered steps with a 1px vertical rail.
- Complete: teal tick (SVG, Phosphor). Current: small pulsing dot (opacity pulse only). Pending: Faint Meta.
- Copy is operational (`Searching catalog`, `Comparing 6 laptops`), not "Unleashing AI magic".

### Timeline (Audit)

- Left column: `HH:MM:SS` Geist Mono.
- Spine: 1px Hairline.
- Event title + compact payload (amount, score, verdict).
- Payment-not-issued events use Block color on the title only.

### Loaders

- Skeletons that match contract rows / timeline rows / amount block. Shimmer via opacity on transform, not a centered circular spinner as the page hero.

### Empty / error

- Compile fail: inline schema issues + "Enter a numeric budget. IntentGuard will not invent one."
- No proposal yet: empty well with next action ("Run the agent").
- Payment UNKNOWN: explicit reconcile control, not a silent retry spinner.

### Icons

- `@phosphor-icons/react`, light/regular, stroke consistent (`1.5`). No emoji in the product UI.

---

## 6. Screen-specific direction

### Screen 1 — Create Intent

Eyebrow: `NEW AUTHORIZATION`.  
Title: "What should the agent be allowed to do?"  
Primary CTA: "Compile intent" then "Confirm contract".  
Right panel fills as fields appear (stagger children). User must confirm before run.

### Screen 2 — Live Agent Execution

Title uses intent goal, not "Dashboard".  
Activity is the main column. When a proposal exists, the side panel shows SKU, amount (mono, large), merchant. CTA: "Send to IntentGuard" if not auto-submitted (prefer auto-submit on proposal).

### Screen 3 — Decision (hero)

This is the screenshot screen.

- Macro amount: `₹58,000` in Geist Mono, `clamp(2.5rem, 6vw, 4.5rem)`.
- Product name beneath in Geist.
- Check stack, then verdict.
- BLOCK: show two-column comparison `Original intent` vs `Proposed action`, then "Payment was not initiated."
- PAUSE: question in body measure (`max-w-[65ch]`), Confirm (teal) / Reject (block outline).

### Screen 4 — Audit Trail

No summary cards row of three. One spine. Latest event at the bottom (chronological) or top (reverse) — pick **oldest at top** so the story reads downward like a log.

---

## 7. Motion and interaction

- Easing: `cubic-bezier(0.32, 0.72, 0, 1)` or spring `stiffness: 100, damping: 20`. No `linear` / `ease-in-out` defaults.
- Animate `transform` and `opacity` only. Never `top`, `left`, `width`, `height`.
- Entry: short fade-up (`translate-y-3`, ~500ms). No blur-on-scroll over large regions (perf).
- `backdrop-blur` only on the floating nav island and modal overlays — not on scrolling lists.
- Stagger activity steps and audit rows (`~60–90ms`).
- Verdict change: layout morph of the stamp color/text, no particle explosion.
- Perpetual motion: only the "current step" pulse and a live clock in audit if needed. Do not animate decorative orbs in the background.
- Isolate animated bits in `'use client'` leaf components.

---

## 8. Copy rules

- Concrete verbs: compile, verify, block, pause, grant, reconcile.
- **Banned filler:** Elevate, Seamless, Unleash, Next-Gen, Magical, Empower, "Scroll to explore".
- **Banned UI chrome:** bouncing chevrons, "Swipe down", emoji stamps (`🚨`).
- Blocked reason names the violated constraint (`Direct flight required`).
- Amounts always with currency and locale-aware grouping (`₹60,000`).

Placeholder people/products: use specific catalog names (Sony WH-1000XM, IndiGo 6E-XXX), never "John Doe" or "Acme Laptop".

---

## 9. Anti-patterns (banned)

- Emojis anywhere in the UI
- Inter / generic system UI fonts as the brand face
- Pure black `#000000`
- Purple/violet AI gradients, neon outer glows, glow buttons
- Oversaturated accents or gradient-fill H1s
- Custom mouse cursors
- Three equal feature cards in a row
- Centered marketing hero on product screens
- Stock shadcn violet + `shadow-md` + `rounded-md` look
- Generic Lucide-heavy illustration as the brand
- Fake round metrics (`99.99%` semantic match) — use real engine numbers (`0.61` → `61%`)
- Overlapping text/image stacks that hide amounts
- `h-screen` full sections
- Agent chat bubbles as the primary authorization UX (a compact log is fine; this is not iMessage)

---

## 10. Implementation notes

- Theme shadcn tokens to this palette; do not leave default zinc-purple.
- CSS variables in `globals.css` for every named color above.
- Geist via `next/font` (Sans + Mono).
- Framer Motion only if listed in `package.json`; otherwise CSS transitions with the cubic-bezier above.
- Light mode is out of scope for MVP. One dark substrate.
