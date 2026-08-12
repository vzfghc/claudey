# Product Specification: Claudey Admin UI (React micro-frontend)

> Current phase: Phase 3/4 — React rebuild live at `/admin`; vanilla admin deleted.

## Vision

The Claudey admin is a local-only server dashboard rebuilt as a React micro-frontend. It provides provider routing configuration, model fallback chains, messaging/voice settings, and a full usage dashboard — all served from the Python backend as a self-contained build with no external runtime deps.

## Design Direction

- **Color**: heat `#ff4d00` is the single interactive accent (replaces Apple Action Blue `#0066cc` and Firecrawl `#fa5d19`). Semantic colors (success `#42c366`, warn `#ecb730`, danger `#eb3424`, info `#9061ff`) exist but are never used for interactive chrome.
- **Typography**: Apple grammar — Inter font (substitutes SF Pro), 17px body, 34px/600/`-0.374px` display heads, `tabular-nums` on numbers, mono for keys/tokens. Weight ladder: 300/400/600/700 — no 500.
- **Layout**: preserved React Sidebar component (easeOutQuint tween, nav-pill breathing glide) + scrollable content area. No decorative shadows or gradients on cards.
- **Anti-AI-slop**: single heat accent, no generic purple/blue gradients, no stock shadcn/tremor themes without customization, no weight 500, token refs not inline hex in components.

## Current Features (Phase 3 — React rebuild)

1. **Providers view** — provider grid with logos + status badges (success/warn/danger); custom-provider dialog (name/base_url/api_key/type + validate/create); combo CRUD dialog + combo cards with `@combo:<id>` token copy.
2. **Model Config view** — 5 role cards (Fallback/Fable/Opus/Sonnet/Haiku) with model + reasoning policy fields; Refresh models button; Web Tools config section; sticky ConfigActionBar (validate/apply/restart).
3. **Messaging view** — Messaging + Voice notes config sections; sticky ConfigActionBar.
4. **Usage view** — UsageHero (preserved ripple rings + count-up + cost row); UsageHeatmap (52-week grid, 5 heat levels, tooltip); UsageTrendChart (tremor AreaChart); UsageDailyTable (shadcn Table); ProviderBreakdown (stacked bar + per-provider tokens).

## Not Yet Ported

- Connected-account OAuth flow (login/disconnect) — Python API endpoints exist but React views are not wired.

## Technical Stack

- **Frontend**: Vite 8.2.1, React 19.2.8, TypeScript strict, Tailwind v4 (CSS-first), shadcn (from `/Users/hanifrestian/shadcnstudio`), tremor 3.18.7, recharts, motion, sonner, Radix UI, lucide-react.
- **Backend**: Python Starlette/FastAPI server serving React build from `admin_ui_dist` at `/admin`. Loopback-only (localhost).
- **Design system**: `docs/design-system.md` — Apple × Firecrawl merge with claudey heat substitution.

## Known Bugs (current iteration)

1. **useConfigForm never calls load() on mount** — `isLoading` starts `true` but no `useEffect(() => load())` triggers the fetch. Model Config and Messaging views render the loading skeleton permanently.
2. **UsageTrendChart passes raw hex to tremor colors prop** — tremor's `colors` expects a palette color name (e.g. `"orange"`), not `"#ff4d00"`. The area chart renders with broken/invisible fill.
3. (Pre-existing, unrelated to UI: 3 Python CI failures — import boundaries ×2, provider_manager warm-refresh.)

## Sprint Plan (current iteration)

### Sprint: Bug Fix — Stuck Skeletons + Chart Color
- Fix `useConfigForm` to call `load()` on mount (add `useEffect`).
- Fix `UsageTrendChart` to use a valid tremor color that maps to heat `#ff4d00`.
- Verify all four views load real data in the live app.
- Commit fixes; update generator-state.md.