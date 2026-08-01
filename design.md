# AIC HRM Pro — Design System "Muc & Thep HRM"

Locked design system for every UI surface of the AIC HRM Pro suite (Odoo OWL
client actions, field widgets, and the Apps Store description page). Produced
by Hallmark (custom theme route, user-approved). Subsequent design work defers
to this file.

## Identity

- **Genre**: modern-minimal (enterprise) · **Tone**: utilitarian-editorial —
  "an audited document, not an AI demo". The UI must read like a verified
  record: data first, zero varnish.
- **Vibe**: ink-on-steel, audited-document, enterprise-calm, no varnish.
- **Axes**: light / grotesk-sans / cool (hue 235).

## Hard bans (AI-slop guard)

Glow, gradients, glassmorphism, sparkle/robot/AI iconography, fake browser or
phone chrome, invented metrics or testimonials, decorative donut charts,
italic headers, bouncy easings, celebratory toasts.

## Tokens

Single source: [`tokens.css`](tokens.css) — three tiers
(primitive -> semantic -> component). Components reference semantic names only
(`var(--color-accent)`); raw OKLCH values never appear in component CSS.

- Paper: steel-tinted near-white 98% (dark mode 16%), hue 235 throughout.
- Accent: ink-blue `oklch(45% 0.14 235)` — the ONLY accent; used for active
  states, links, one primary action per screen. Footprint <= 5%.
- **Status (RAG) tokens are data colors, not accent**: `--status-green/amber/red/neutral`.
  Every status indicator pairs color with a shape or icon (dot / triangle /
  square) so meaning survives color-blindness. APCA >= 3:1 on paper.
- Numbers always render in `--font-data` (IBM Plex Mono) with `font-variant-numeric: tabular-nums`.

## Typography

IBM Plex superfamily (full Vietnamese subset; `IBM Plex Sans JP` for the ja
locale — never let ja fall back silently):

- Display: IBM Plex Sans 600/700, letter-spacing -0.02em, roman only.
- Body: IBM Plex Sans 400, >= 14px floor.
- Data/code: IBM Plex Mono.

## Surfaces

1. **Leadership cockpit** (OWL client action): "reading desk" layout — row 1
   cycle health strip (committed score / overall / check-in rate, large mono
   numerals); center RAG heatmap (department x objective, shape+color cells);
   right rail risk queue (alerts, stalled KRs). Charts follow the dataviz
   skill at build time.
2. **Alignment tree**: indented tree with vertical rails (no bubble charts).
   Node = code · name · owner avatar · RAG dot · mono score · thin progress
   bar. Expand/collapse via opacity <= 150ms, no layout animation.
3. **9-box grid**: strict 3x3, labelled axes, draggable employee cards; a drop
   into another cell opens a mandatory justification modal. Full 8-state
   styling on the draggable card.
4. **Check-in flow**: single column, <= 5 fields (new value · confidence 1-10
   slider with worded labels · blocker textarea · computed RAG preview).
   Submit = silent success ("Recorded HH:MM" badge next to the button).
5. **Personal KPI scorecard**: table-first; numeric columns right-aligned in
   mono; a checksum row "SUM = 100% OK/FAIL" turns red on mismatch; thin bars
   + numbers, no decorative donuts.
6. **Apps Store page** (`static/description/index.html`): macrostructure
   Workbench — real product screenshots as hero (no fake chrome), no nav
   (embedded page), single-line footer, honest copy in English.

Native Odoo form/list views keep the standard frame and consume only the
status tokens and badge widgets.

## Responsive — mobile is mandatory (user directive 2026-08-02)

Every surface must work on phones. Hallmark's mobile floor applies to ALL
custom UI, verified at **320 / 375 / 414 / 768 px** before a checkpoint closes:

- No horizontal page scroll; root `overflow-x: clip`; wide content (tables,
  heatmap, tree) scrolls inside its own container.
- Grid tracks that carry content use `minmax(0, 1fr)`; headers wrap via
  `overflow-wrap: anywhere; min-width: 0`.
- Touch targets >= 44px; no two-line buttons/links.
- Per-surface collapse: cockpit health strip stacks vertically; heatmap
  becomes a scrollable card list grouped by department; alignment tree keeps
  indent rails with horizontal pan; 9-box switches drag to select-then-place
  (tap card -> tap cell -> justification modal); check-in form is already
  single-column (mobile-first); scorecard table gets sticky first column +
  horizontal scroll within the card.
- Odoo backend shell is responsive by default — custom OWL components must not
  break it (test in Odoo's mobile viewport, plus 2 mobile tours at CP7).

## Interaction

- Every interactive widget ships all 8 states: default · hover ·
  :focus-visible · active · disabled · loading · error · success.
- Empty states instruct the next action, never bare "No data".
- Motion: exactly 3 primitives — rag-pulse-once (on score change) · row-hover
  1px lift · instant focus ring. `prefers-reduced-motion` collapses all to
  <= 150ms opacity.
- Silent success over toasts; optimistic update + undo over confirm dialogs.

## Process

- Slop test (58 gates) runs before CP7 closes; stamp + `.hallmark/log.json`
  maintained at project root.
- i18n: all user-facing strings are English source translated via
  `i18n/vi.po` (complete) and `i18n/ja.po` (draft, flagged until native
  review).
