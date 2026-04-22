# CVMaker — Design System

The product is about documents. The UI should feel like a good writing app, not a dashboard.

## Principles

1. **Type is the hero.** CVs are text. The editor should treat type like a luxury goods catalog treats photography — large, confident, generously spaced. Everything else is chrome.
2. **One accent, used sparingly.** The interface is near-black on near-white. A single warm accent appears on the primary action, the active nav item, and the focus ring. Never on backgrounds or decorative fills.
3. **Restraint over density.** A CV editor with thirty buttons visible is a CV editor no one finishes. Progressive disclosure: show the fields, hide the knobs, surface the knobs when they're needed.
4. **Live preview is the money interaction.** A split pane — editor on the left, the actual rendered CV on the right, updating as you type. This is the single most important thing the UI does. Build the app around it.
5. **Dark mode from day one.** Not a retrofit. Tokens are defined in both modes; every component is tested in both.
6. **Motion is functional, never decorative.** Reordering a section glides. A newly-added entry flashes once. That's the budget.

## Reference points

- **Linear.app** — restraint, keyboard-first, command palette. The bar.
- **Stripe Press / Stripe dashboard** — typography, editorial spacing, serif display fonts over a geometric sans.
- **Vercel.com** — the dark mode + mono-accent aesthetic at its best.
- **Claude.ai** — warm off-white, generous line-height, unobtrusive controls.
- **Raycast** — the command palette and keyboard-shortcut affordances.
- **Reflect / iA Writer** — how a writing tool respects its content.

Explicit anti-references: Canva, Zety, ResumeGenius. Loud gradients, emoji badges, "1 person is viewing this page" urgency bars. We are not them.

## Tokens

### Color

Light mode is the default. Dark mode uses the same semantic tokens remapped.

| Token | Light | Dark | Use |
| --- | --- | --- | --- |
| `--bg` | `#FAFAF7` | `#0E0E0C` | Page background. Warm off-white, warm off-black. |
| `--surface` | `#FFFFFF` | `#17171410` | Cards, editor pane. |
| `--surface-2` | `#F4F3EE` | `#1F1F1C` | Inputs, secondary panels. |
| `--border` | `#E7E5DE` | `#2A2A26` | Hairlines. `1px`, never thicker. |
| `--text` | `#17171A` | `#ECECE8` | Body. |
| `--text-muted` | `#6B6B68` | `#9A9A95` | Labels, metadata, help text. |
| `--accent` | `#C2410C` | `#F97316` | Primary action, focus ring, active state. One color, chosen warm. |
| `--accent-ink` | `#FFFFFF` | `#17171A` | Text on accent. |
| `--danger` | `#991B1B` | `#F87171` | Destructive confirm only. |

The accent is a burnt orange (`#C2410C`). Rationale: cool blues are the default choice and therefore invisible; a warm orange reads as craft and editorial, matches the product's document-first personality, and is still professional enough to not feel like a consumer app.

### Type

```
Display   — "Fraunces"        variable serif, weight 420, optical sizing on
Body      — "Inter"            variable sans, weight 400 / 500 / 600
Mono      — "JetBrains Mono"   weight 400, for YAML, keys, shortcuts
CV output — Theme-defined       the rendered CV picks its own typography
```

`Fraunces` for display gives the app an editorial, book-jacket feel without being stuffy. `Inter` for body is the safe, excellent choice. Both are self-hosted (`/static/fonts/`) for privacy (no Google Fonts request) and determinism.

Scale (8pt base, 1.25 minor-third ratio):

```
xs   12 / 16
sm   14 / 20
base 16 / 24        — body default
lg   18 / 28
xl   20 / 28
2xl  24 / 32
3xl  30 / 40
4xl  36 / 44
5xl  48 / 56        — hero h1
6xl  60 / 68        — marketing page only
```

### Spacing

8pt grid. Named stops: `1 (4) · 2 (8) · 3 (12) · 4 (16) · 6 (24) · 8 (32) · 12 (48) · 16 (64) · 24 (96)`. No off-grid values. Form field vertical rhythm: 12px inside, 24px between fields, 48px between sections.

### Radius

```
sm  4px   — inputs, chips
md  8px   — buttons, cards
lg  12px  — modals, large surfaces
full      — avatar, toggle switch
```

Never more than one radius scale in the same component.

### Elevation

Shadows are soft and colored with the page background, not black. Three levels.

```
0   none                                                       — default
1   0 1px 2px rgb(0 0 0 / 0.04), 0 1px 1px rgb(0 0 0 / 0.02)   — card
2   0 8px 24px rgb(0 0 0 / 0.06), 0 2px 4px rgb(0 0 0 / 0.03)  — dropdown, popover
```

In dark mode, shadows go away entirely; separation is borders only.

## Frontend stack

**Tailwind CSS** + **HTMX** + **Alpine.js**.

Rationale: we want a single-codebase Django app (no SPA split), a design system that's easy to evolve, and live interactivity (reorder-by-drag, live preview, inline edits) without building a React build pipeline for every screen.

- **Tailwind 3.4** drives every style. Tokens above are declared as `tailwind.config.js` theme extensions + CSS variables. We stop writing `app.css`.
- **HTMX** handles server-rendered partial updates: reorder a section, add an entry, toggle a field — the server returns HTML, the page swaps a fragment. No JSON-ferrying, no client state machine, no lost scroll positions.
- **Alpine.js** handles local-only interactivity: disclosures, tabs, tooltips, the command palette, the dark-mode toggle.
- **django-cotton** (or django-components) for first-class component templates so we can write `{% c "button" variant="primary" %}Save{% endc %}` instead of repeating markup.
- **No jQuery, no Bootstrap.** Both are removed in Phase 1.
- **One build step**: `npm run build` produces `/static/dist/app.css` and a tiny `app.js` (Alpine + HTMX); Whitenoise serves it with a hash. No webpack, no Vite — `@tailwindcss/cli` + `esbuild` are enough.

## Core components (in order of build)

1. **Button** — primary, secondary, ghost, destructive. Sizes sm/md/lg. Loading state. Icon slot.
2. **Input, Textarea, Select** — single look, labels above, help text below, error state with inline message, monospace variant for YAML.
3. **Card** — the primitive everything else is built from. Padded surface, optional header with action slot.
4. **Nav** — sticky top bar, product wordmark, primary nav, user menu. Collapses to a drawer under 768px.
5. **Sidebar** — contextual, collapsible, for the editor.
6. **Split pane** — editor on the left, live preview on the right. The one bespoke component. Resizable, collapsible, persists width to localStorage.
7. **Command palette** — ⌘K / Ctrl-K. Jump to any CV, any section, any entry; run `New CV`, `Switch language`, `Duplicate`. Keyboard-first.
8. **Toast** — non-modal, bottom-right, auto-dismiss. For "CV rendered", "Entry translated", "Saved".
9. **Modal** — used sparingly. Destructive confirms, first-run tour.
10. **Drag handle** — for reordering sections and entries. Uses `@dnd-kit` equivalent in Alpine (Sortable.js).

## Screens

- **Marketing home** (`/`) — large Fraunces hero, one sentence, a screenshot of the split-pane editor with an animated preview, two CTAs (Sign up · See demo). One scroll. No carousel. No testimonials until we have real ones.
- **Dashboard** (`/app`) — list of CVs as cards with a 50px-wide thumbnail of the real PDF. "New CV" card first. Filter by language chip.
- **Editor** (`/app/cv/<id>`) — the money screen. Left pane: collapsible accordions for Info / Sections / Design / Locale / Settings. Right pane: live PDF preview. Top bar: CV name, language switcher, "Download", "Share link". Keyboard: `⌘S` save, `⌘K` palette, `⌘E` toggle editor, `⌘P` toggle preview.
- **Library** (`/app/entries`) — a table of all your entries across all CVs, grouped by type, with a translation-completeness indicator ("EN ✓ · ES ✓ · FR ○"). Filter, search.
- **Settings** (`/app/settings`) — account, password, email, default language, billing (later).

## Accessibility

Non-negotiable, and not a separate phase — it's part of the component definition.

- WCAG 2.2 AA contrast on all tokens. We spot-check in CI.
- Every interactive element is focusable and has a visible focus ring using `--accent`.
- Motion respects `prefers-reduced-motion`.
- The editor is operable keyboard-only; drag-reorder has keyboard-arrow alternatives.
- Semantic HTML — `<nav>`, `<main>`, `<article>` — not div soup.
- Form fields are labeled, errors are `aria-live="polite"`.

## Definition of done (design)

The design system ships when:

1. `tailwind.config.js` declares the tokens above.
2. `docs/DESIGN.md` (this file) stays truthful.
3. `/components` demo page renders every core component in both light and dark mode, and is the first page we `curl` in CI to catch regressions.
4. The editor's split-pane + live preview works on a cold page load in under 2 seconds on a mid-range laptop.
5. A Playwright snapshot test exists per component; diffs fail CI.
