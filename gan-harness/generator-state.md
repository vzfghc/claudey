# Generator State — Phase 3 Views Rebuilt

> Track: React micro-frontend (docs/design-system.md + docs/frontend-scaffold-plan.md).
> Branch: `feat/phase-a-free-providers` · HEAD after this iteration.
> Status: Phase 3 (Views rebuilt) implemented — Providers, Model Config, Messaging, Usage.

## What Was Built

- **shadcn primitive layer** (`components/ui/shadcn/`):
  - `card.tsx`, `input.tsx`, `label.tsx`, `badge.tsx`, `textarea.tsx`,
    `switch.tsx`, `separator.tsx`, `skeleton.tsx`, `dialog.tsx`, `tooltip.tsx`,
    `table.tsx`, `select.tsx`, `checkbox.tsx`, `tabs.tsx`, `sonner.tsx`
  - All adapted from `/Users/hanifrestian/shadcnstudio` onto claudey tokens
    (heat `#ff4d00`, Apple typography, hairline borders, lg radius cards).
- **API layer** (`api/client.ts` + `api/types.ts`):
  - Full typed client: config, validate, apply, restart, models, refresh,
    combos CRUD, custom providers CRUD, provider test, local-status,
    connected-account auth (login/cancel/disconnect).
  - Types for all 15+ admin API payloads (ConfigPayload, Combo, ProviderStatus, etc.).
- **Config form system** (`shared/form/` + `hooks/use-config-form.ts` + `lib/config.ts`):
  - `ConfigFieldRow` — renders any field type (text/secret/number/boolean/
    model/optional_model/select/textarea) with correct wire-value normalization.
  - `ConfigSection` — section wrapper with advanced toggle.
  - `ConfigActionBar` — sticky validate/apply/restart bar with dirty count.
  - `ModelCombobox` — searchable model dropdown with arrow-key nav + custom slug entry.
  - `useConfigForm` hook — loads `/admin/api/config`, tracks dirty state,
    validate/apply/restart via typed client.
- **Providers view** (`views/providers-view.tsx` + `providers/`):
  - Provider grid with logo, status badge (semantic colors), test/configure buttons.
  - Custom provider dialog (name/base_url/api_key/type/model_id + validate + create).
  - Combo dialog (name/nodes/enabled + validate + create/edit/delete).
  - Combo cards with copyable `@combo:<id>` token, edit/delete actions.
- **Model Config view** (`views/model-config-view.tsx`):
  - 5 role cards (Fallback/Fable/Opus/Sonnet/Haiku) with model + reasoning fields.
  - Refresh models button with toast feedback.
  - Web Tools config section.
  - Sticky action bar (validate/apply/restart).
- **Messaging view** (`views/messaging-view.tsx`):
  - Messaging + Voice notes config sections.
  - Sticky action bar.
- **Usage view** (rebuilt `views/usage-view.tsx` + `usage/`):
  - Preserved `UsageHero` (ripple rings, count-up, period tabs, cost row).
  - `UsageHeatmap` — 52-week grid with 5 heat levels + tooltip.
  - `UsageTrendChart` — tremor `AreaChart` with heat `#ff4d00` fill.
  - `UsageDailyTable` — shadcn Table with totals row + per-day breakdown.
  - `ProviderBreakdown` — stacked bar + per-provider token share.
- **App shell** (`app.tsx`):
  - All 4 views wired (Providers/Model Config/Messaging/Usage).
  - `TooltipProvider` wrapping the app.
  - `Toaster` (sonner) mounted at root.
  - Theme toggle (light/dark with localStorage persistence).

## What Changed This Iteration

- Added: 15 shadcn primitives adapted to claudey tokens.
- Added: Full typed API client (15+ endpoints).
- Added: Config form system (field types, dirty state, validate/apply/restart).
- Added: Providers view (grid, custom provider dialog, combo CRUD).
- Added: Model Config view (role cards, refresh models, web tools).
- Added: Messaging view (messaging + voice sections).
- Rebuilt: Usage view (tremor AreaChart, heatmap, daily table, provider breakdown).
- Added: Radix UI deps (dialog, tabs, label, checkbox, switch, select, separator, tooltip).
- Added: sonner for toast notifications.
- Preserved: Sidebar choreography, UsageHero ripple math (unchanged).

## Known Issues

- Bundle is 1.2MB (347KB gzip) — tremor/recharts is heavy; code-splitting deferred.
- Beam diagram not re-homed yet (still served via `beam.bundle.js` at `/admin`).
- Connected-account OAuth flow not ported (providers view shows remote/local/custom only).
- 3 pre-existing CI failures remain (import boundaries ×2, provider_manager warm-refresh ×1).
- The eval rubric (`gan-harness/eval-rubric.md`) scores the vanilla admin animation
  patterns, NOT the React rebuild — it's stale relative to this Phase 3 work.

## Dev Server

- URL: http://127.0.0.1:8090/admin/ui (React app) and http://127.0.0.1:8090/admin (vanilla)
- Status: running
- Command: `uv run hans-server` (background, log at `/tmp/claudey-admin-server.log`)
- Build: `cd src/claudey/api/admin_static/admin-ui && npm run build` → copies to `admin_ui_dist`
- Typecheck: `npm run typecheck` — passes clean
