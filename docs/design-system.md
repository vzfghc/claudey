# Claudey Design System — Apple × Firecrawl

> **Status:** Design only. The canonical token/component reference for the `admin-ui` refactor.
> **Sources:** Apple wins **typography & hierarchy**; Firecrawl wins **component architecture, motion system, and directory structure**. This doc is the merge, with claudey's brand substituted.
> **Audience:** Downstream generator agents building the `admin-ui` package.

## 1. Brand rules (non-negotiable)

- **Main interactive color is always claudey heat `#ff4d00`.** It replaces every Apple Action Blue (`#0066cc`) and every Firecrawl main (`#fa5d19`) anywhere the source docs name a primary/action color.
- **Single interactive accent.** Apple's iron rule: every click-me signal (links, CTAs, focus ring) uses `heat` and nothing else. Semantic/status colors exist but are never interactive chrome.
- **Token referencing.** Never inline hex in components — use `{token.refs}` / Tailwind theme vars (Apple §Iteration Guide rule 3, Firecrawl color mapping pattern).
- Follow Apple best practice for semantic use and code correctness (states: default/active/pressed only — no hover documentation; `transform: scale(0.95)` press state everywhere).

## 2. Color tokens

| Role | Token | Value | Notes |
|---|---|---|---|
| Heat primary | `--heat` | `#ff4d00` | the ONE interactive accent (replaces `#0066cc` and `#fa5d19`) |
| Heat focus | `--heat-focus` | `#ff6a2b` | brighter sibling → focus ring (mirrors Apple `primary-focus`) |
| Heat on dark | `--heat-on-dark` | `#ff7a3d` | inline links on dark tiles (mirrors Apple `primary-on-dark`) |
| Heat soft | `--heat-soft` | `#ffaa40` | beam gradient stop / warm highlights |
| Heat alpha | `heat-4…heat-100` | `--heat` @ 4–100% | Firecrawl heat ladder |
| Status → semantic only | success `#42c366` · warn `#ecb730` · danger `#eb3424` · info-aux `#9061ff` | Firecrawl accents | never used for primary actions |
| Alpha overlays | `black-alpha-1…88`, `white-alpha-56/72` | Firecrawl | overlays/layering |
| Canvas | `--canvas` | `#ffffff` | dominant surface |
| Parchment | `--parchment` | `#f5f5f7` | alternating tiles, footer, sub-nav |
| Pearl | `--pearl` | `#fafafc` | secondary/ghost button fill |
| Tile 1/2/3 | `#272729` / `#2a2a2c` / `#252527` | Apple | dark tiles (dark mode) |
| Pure black | `--surface-black` | `#000000` | top nav only |
| Ink / body | `--ink` | `#1d1d1f` | voice of text (light surfaces) |
| Ink muted | `--ink-muted-48` | `#7a7a7a` | disabled text, fine-print |
| Body muted dark | `--body-muted-dark` | `#cccccc` | secondary copy on dark |
| Divider soft | `--divider-soft` | `rgba(0,0,0,0.04)` | ring on secondary buttons |
| Hairline | `--hairline` | `#e0e0e0` | 1px card/chip borders |

> Remap existing admin vars into this system: `--panel/--card/--line/--muted/--text-secondary` → tokens above.

## 3. Typography — Apple adopted whole

| Token | Size / W / LH / LS | Use |
|---|---|---|
| `hero-display` | 56 / 600 / 1.07 / **−0.28px** | landing/empty states |
| `display-lg` | 40 / 600 / 1.10 / 0 | view/tile headlines |
| `display-md` | 34 / 600 / 1.47 / **−0.374px** | section heads |
| `lead` | 28 / 400 / 1.14 / +0.196px | view lead-ins |
| `tagline` | 21 / 600 / 1.19 / +0.231px | sub-tile, sub-nav |
| `body` | **17 / 400 / 1.47 / −0.374px** | default — never 16px |
| `body-strong` | 17 / 600 / 1.24 / −0.374px | emphasis |
| `caption` | 14 / 400 / 1.43 / −0.224px | secondary |
| `caption-strong` | 14 / 600 / 1.29 / −0.224px | card titles, labels |
| `fine-print` | 12 / 400 / 1.0 / −0.12px | footer/meta |
| `nav-link` | 12 / 400 / 1.0 / −0.12px | sidebar/nav |
| `dense-link` | 17 / 400 / **2.41** / 0 | dense link columns |
| `mono` | Geist Mono / Roboto Mono | tokens, hashes, keys (Firecrawl) |

**Rules:** weight ladder **300 / 400 / 600 / 700 — no 500**. Body 400; display 600; strong 600; rare 300 for airy moments. Negative letter-spacing ≥17px only. `font-variant-numeric: tabular-nums` on numbers. Inter substitutes SF Pro (tighten body LH ~0.03, display tracking −0.01em).

## 4. Spacing & sizing

- **Apple 8px base**: `xxs 4 · xs 8 · sm 12 · md 17 · lg 24 · xl 32 · xxl 48 · section 80`.
- **Explicitly rejected: Firecrawl pixel-px sizing override** (`sizes = {N: Npx}`). It silently breaks every shadcn/magicui/tremor default (`h-9`→9px). Use standard Tailwind spacing with the 8px rhythm.
- Section vertical padding 80px; card padding 24px; button 8–11px × 15–22px; touch target ≥44×44px.

## 5. Radius (Apple grammar)

`none 0 · xs 5 · sm 8 · md 11 · lg 18 · pill/full 9999`
- `pill` = the action signal (CTAs, chips, search, segmented control).
- `sm` = compact utility, `lg` = utility cards. Don't mix grammars.

## 6. Elevation

- **Marketing/hero:** Apple-exact. No decorative shadows/gradients; the single `rgba(0,0,0,0.22) 3px 5px 30px` reserved for logo/product renders; color-change-is-the-divider; frosted sticky bars `backdrop-filter: saturate(180%) blur(20px)`.
- **Tool surfaces (admin, documented divergence):** minimal **2-step ramp** — one soft card shadow + hairlines; never stack shadows.

## 7. Motion

- **Timing:** default `cubic-bezier(0.25, 0.1, 0.25, 1)`; durations `n × 50ms` (`duration-4`=200ms quick, `duration-10`=500ms moderate).
- **Keyframes (Firecrawl):** `fade-in`, `fade-up`, `accordion-down/up`, `button-press`, `screenshot-scroll`.
- **Engine:** `motion` in React; all loops gated behind `prefers-reduced-motion`.
- **Preserved choreography:** sidebar easeOutQuint tween + nav-pill breathing glide (specs in scaffold-plan §5).

## 8. Component architecture (Firecrawl)

```
components/
├── ui/        shadcn/ · magic/ · tremor/ · motion/
├── shared/    icons/ · buttons/ · cards/ · effects/ · layout/ · ui/
├── app/       providers/ · usage/ · messaging/ · model-config/ · scout/
└── providers/ theme · motion
```

**Conventions:** PascalCase files/exports, kebab-case dirs, index barrels; shadcn in `ui/shadcn`, magic in `ui/magic`, tremor in `ui/tremor`, motion in `ui/motion`; shared/brand in `shared/`, page-specific in `app/`; Tailwind utilities only (no CSS modules/inline styles except the two preserved animated components); import alias `@/components/...`.

## 9. Component grammars (Apple, heat substituted)

| Grammar | Spec |
|---|---|
| `button-primary` (HeatButton) | `--heat` bg, white text, `pill`, 11×22, press `scale(0.95)`, focus 2px `--heat-focus` |
| `button-secondary-pill` (GhostPill) | transparent, 1px `--heat` border, `--heat` text, `pill` |
| `button-dark-utility` | `--ink` bg, white text, `sm`, 8×15 |
| `button-pearl-capsule` | `--pearl` bg, `--ink-muted`, `md`(11px), ring `--divider-soft` |
| `button-store-hero` (large) | `--heat` bg, 18/300, `pill`, 14×28 |
| `button-icon-circular` | 44×44, translucent chip @64%, `full` |
| `text-link` / `text-link-on-dark` | `--heat` on light, `--heat-on-dark` on dark tiles |

## 10. Do / Don't (merged)

- ✓ single heat accent for all interactive; ✓ body 17px; ✓ 600 display with negative tracking; ✓ `pill` for actions; ✓ one product shadow only; ✓ `scale(0.95)` press; ✓ dark top nav; ✓ token refs everywhere.
- ✗ second accent for chrome; ✗ shadows on cards/buttons/text; ✗ decorative gradients; ✗ weight 500; ✗ rounding full-bleed tiles; ✗ body line-height <1.47; ✗ mixing radii grammars; ✗ Firecrawl pixel-px sizing.