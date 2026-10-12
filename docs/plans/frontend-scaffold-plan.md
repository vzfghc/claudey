# Frontend Scaffold Plan — claudey admin UI

> **Status:** Design only. Gates the frontend refactor week (before defork). Not implemented.
> **Sources:** `docs/design-system.md`. Companion plan to the token/component reference in that file.
> **Audience:** Downstream generator agents building the `admin-ui` package.

## 1. Decisions (user-approved)

| # | Decision | Resolution |
|---|---|---|
| 1 | Bundler | **Vite 8 `@latest`** (create-vite React-TS template) |
| 2 | UI framework | React 19 (already in `beam/`), `createRoot`, ref-as-prop |
| 3 | Styling | Tailwind CI — **v4 via `@tailwindcss/vite`** primary; pinned fallback `tailwindcss@3.4.17` + postcss if tremor/magicui interop fails (verify in Phase 1 spike) |
| 4 | shadcn/ui | **Sourced locally from `/Users/hanifrestian/shadcnstudio`** (`components/ui/*` catalog + `components.json` structure). Do NOT pull from the remote registry; copies come from the local library |
| 5 | magicui | **Fetch via MCP** during implementation; vendor into `components/ui/magic/` |
| 6 | tremor | Setup per **https://blocks.tremor.so/getting-started**. Install `@tremor/react` + peer deps exactly as that page lists; pin exact command in Phase 1 |
| 7 | Motion | `motion` (already in `beam/`), `motion/react` |
| 8 | Dependencies | **Install when applicable** — explicit `npm install` step at the top of each phase |
| 9 | Brand color | Every apple blue (`#0066cc`) and firecrawl main (`#fa5d19`) → **claudey heat `#ff4d00`**. Semantic colors + token referencing follow **Apple best practices** (single interactive accent; `{token.refs}` everywhere; never inline hex) |
| 10 | Vendored beam | If `animated-beam` is not delivered as a tool component at implementation time, **reimport the original magicui `AnimatedBeam`** (via magicui MCP/registry) and re-apply the existing `measureKey` prop patch for drag tracking |
| 11 | Key integration decision | **PICKED (recommended): dist-directory serving** (`admin_ui_dist/` + entry `?v=` cache-bust). Rejected the single-file IIFE (loses code-splitting, bloats entry) |

## 2. Current state (verified)

| Surface | Stack | Build | Serve |
|---|---|---|---|
| `admin_static/index.html`, `admin.css`, `admin.js`, `admin-animations.*` | Vanilla JS + hand CSS | none | static whitelist, `?v=__ASSET_VERSION__` |
| `admin_static/beam/` | Removed in Sprint 8; no longer part of the serving surface | retired | none |

No Tailwind engine (only `tailwind-merge`), no shadcn/magicui/tremor yet.

## 3. Directory structure (Firecrawl architecture)

```
src/claudey/api/admin_static/admin-ui/
├── package.json            # vite@8, react@19, tailwind, motion, @tremor/react
├── vite.config.ts          # @tailwindcss/vite + react + @/ alias
├── tsconfig.json / tsconfig.node.json
├── components.json         # shadcn config (style new-york, aliases @/*)
├── index.html
├── build.mjs               # Vite build → copy dist/* into ../admin_ui_dist
└── src/
    ├── main.tsx            # createRoot(<App/>)
    ├── app.tsx             # shell: Sidebar + Topbar + view switch
    ├── styles/
    │   ├── globals.css     # @import "tailwindcss", layer utilities
    │   └── tokens.css      # CSS custom properties (design-system.md)
    ├── components/
    │   ├── ui/
    │   │   ├── shadcn/     # from local shadcnstudio: button, input, card, tabs, dialog, toast, badge, table, select, switch…
    │   │   ├── magic/      # via MCP: animated-beam, dot-pattern, ripple, dock, shiny-text…
    │   │   ├── tremor/     # LineChart, BarChart, AreaChart, ProgressBar
    │   │   └── motion/     # fade-in, rise-in, view-in wrappers
    │   ├── shared/
    │   │   ├── icons/      # brand + utility (index.ts barrel)
    │   │   ├── buttons/    # HeatButton, GhostPill, UtilityButton, PearlCapsule, IconCircular
    │   │   ├── cards/      # Tile, SurfaceCard, StatCard
    │   │   ├── effects/    # Ripple(hero), Beam, Scout, Toast
    │   │   ├── layout/     # AppShell, Sidebar, Topbar, ViewSwitch
    │   │   └── ui/         # SegmentedControl, CountUp
    │   ├── app/
    │   │   ├── providers/  # grid + config forms
    │   │   ├── usage/      # UsageHero (total-token), heatmap, charts, table
    │   │   ├── messaging/
    │   │   ├── model-config/
    │   │   └── scout/
    │   └── providers/      # ThemeProvider (light/dark), MotionProvider
    ├── lib/
    │   ├── utils.ts        # cn() from local shadcnstudio
    │   ├── api.ts          # typed /admin/api/* fetchers
    │   └── format.ts       # formatTokens, scoutCompact/USD/IDR ports
    ├── hooks/              # useReducedMotion, useCountUp, useTween
    └── types/              # BeamProvider, UsagePayload, DashboardPayload…
```

> **Local shadcn sourcing:** copy the needed primitive/components from `/Users/hanifrestian/shadcnstudio/components/ui/*.tsx` (confirmed present: `number-ticker.tsx`, `marquee.tsx`, `background-beams.tsx`, `border-beam.tsx`, `animated-beam.tsx`) + the required deps (`class-variance-authority`, `clsx`, `tailwind-merge`, `lucide-react`, Radix packages). `components.json` style: `new-york`, baseColor `neutral`, cssVariables true.

## 4. Build & serve contract

- `admin-ui` builds with Vite 8; `build.mjs` copies the emitted `dist/` (hashed JS/CSS chunks) into `admin_ui_dist/` under `admin_static/`.
- `admin_routes.py`: add `admin_ui_dist/` to the administrable asset directory (served via `/admin/assets/*`); keep the `?v=__ASSET_VERSION__` cache-bust on the entry HTML. The `asset_version()` mechanism already reads `pyproject.toml` at serve time.
- Offline-safe: all JS/CSS self-hosted; no runtime CDN.
- The former beam prototype was removed in Sprint 8; its planned bundle is no longer served.

## 5. Preservation contract (components NOT redesignable)

### 5a. Sidebar + nav-pill animation (`shared/layout/Sidebar.tsx`, `hooks/useTween.ts`)
Port `admin-animations.js` + related `admin.css` exactly:

| Behavior | Spec |
|---|---|
| Collapse/expand | rAF per-frame width tween, `easeOutQuint`, **collapse 350ms / expand 220ms**; writes width + padding + `--sidebar-w` + label/budget opacity + nav gap/pad + label width |
| Label/budget fade | fade ends at 120px / 170px (`labelOpacityFor`/`budgetOpacityFor`) |
| Nav pill glide | active orange pill + hover grey pill; `easeOutQuart` 160ms; **sine scale dip anchored to travel progress, `PILL_DIP = 0.07`**; retarget-safe (never restarts, no snap) |
| Snap mode | `snapSidebar` under `prefers-reduced-motion` and `max-width: 900px` |
| A11y | `aria-expanded` on toggle, `aria-hidden` on pills |
| Brand mark hover | `rotate(-4deg) scale(1.06)` + soft shadow |
| Persistence | `claudey.sidebar.collapsed` localStorage key |

### 5b. Total-token hero (`app/usage/UsageHero.tsx`)
| Behavior | Spec |
|---|---|
| Ripple rings | 8 circles, `size = 140 + i*70px`, `opacity = max(0.08, 0.4 − i*0.045)`, delay `i*0.06s`, ripple `3.2s cubic-bezier(0.4,0,0.2,1)` scale `1→0.78→1`, mask-gradient fade |
| Period segmented control | sliding pill indicator (`left`/`width` transition), separators, Total/24h/7d/30d |
| Number | count-up, `tabular-nums`, compact formatter (`1.0M`, `9.1k`) |

### 5c. Everything else — rebuild to the design system
Provider grid, config forms, combo cards → shadcn primitives + heat buttons. Usage charts → tremor. Heatmap/table → shadcn `Table` + tremor; keep the per-row tint tween. Toasts → sonner with swipe-to-dismiss + snap-back curves preserved. Buttons → 5 Apple grammars as `Button` variants (with heat substituted). Typography everywhere → Apple type tokens (17px body, 600 display, negative tracking, no 500).

## 6. Phases (each shippable; install deps first)

### Phase 1 — Foundation
1. `npm create vite@latest admin-ui -- --template react-ts` (Vite 8) then `npm install`.
2. Add `tailwindcss @tailwindcss/vite` (or `tailwindcss@3.4.17 postcss autoprefixer` if fallback) + `motion` + `clsx tailwind-merge` + `lucide-react`.
3. Author `tokens.css` + Tailwind theme per `design-system.md`.
4. Copy shadcn primitives from local `/Users/hanifrestian/shadcnstudio`.
5. **Verify tremor setup** against https://blocks.tremor.so/getting-started; install `@tremor/react` + peers exactly as listed.
6. Decision gate → wire `build.mjs` + `admin_routes.py` dist-serving + `/admin` smoke test.

### Phase 2 — Shell + preserved components
7. Port `AppShell` + `Sidebar` (5a). 8. Port `UsageHero` (5b). 9. `ThemeProvider` light/dark + reduced-motion + mobile snap.

### Phase 3 — Views rebuilt
10. Providers view (grid + forms; re-home beam into `ui/magic/animated-beam` — reimport magicui original + `measureKey` patch).
11. Usage view (tremor charts + heatmap + table + hero).
12. Model config + messaging (shadcn form system).

### Phase 4 — Polish, a11y, CI, sunset
13. Reduced-motion audit, keyboard nav, contrast.
14. Retire vanilla `admin.js`/`admin.css`/`admin-animations.*`; beam was removed in Sprint 8.
15. `./scripts/ci.sh` green; add admin-ui build to CI as committed-artifact check.

## 7. Testing
- Unit: `cn()`, formatters, count-up, tween math (sidebar/pill easing, travel-anchored dip).
- Component: Sidebar collapse/expand (reduced-motion + snap), pill glide retarget, UsageHero ripple/count-up, each button variant.
- Integration: `/admin` renders against live `/admin/api/*`; view switching; dark mode.
- E2E (Playwright): load /admin, switch views, collapse sidebar, open usage, no console errors.

## 8. Risks
- Tailwind v4 × tremor/magicui interop → Phase 1 spike; fallback v3.4.17.
- Firecrawl pixel-px sizing → deliberately excluded (see design-system §Spacing).
- Losing preserved choreography → Phase 2 ports before any redesign; specs above = acceptance tests.
- Local shadcn copies may reference `shadcnstudio.com` email/license registry → only use locally-present files; record missing components to fetch via MCP/registry.
- Version bump on main: `admin_static/` + `admin_routes.py` + `pyproject.toml` → bump per CLAUDE.md at land time.

## 9. Success criteria
- [ ] `/admin` served from new React app, offline-safe, cache-busted, old vanilla assets removed
- [ ] Sidebar choreography identical (350/220ms easeOutQuint; pill dip 0.07 travel-anchored)
- [ ] Total-token ripple/count-up visually identical
- [ ] Every apple/firecrawl blue→`#ff4d00` substitution; semantic token use per Apple practice
- [ ] `./scripts/ci.sh` green; shadcn/magicui/tremor compile clean