# Generator State — Frontend Scaffold Iteration (admin-ui)

> Track: React micro-frontend scaffold (docs/design-system.md + docs/frontend-scaffold-plan.md).
> Branch: `feat/phase-a-free-providers` · HEAD after this iteration.
> Status: Phase 1 (Foundation) + Phase 2 (Shell + preserved components) implemented.

## What Was Built

- **Two reference docs for downstream generator agents:**
  - `docs/design-system.md` — Apple × Firecrawl merge: heat `#ff4d00` as the single accent (replaces apple blue + firecrawl main), Apple typography/hierarchy (17px body, weight ladder 300/400/600/700, negative tracking), radius grammar, elevation, n×50ms motion, component grammars.
  - `docs/frontend-scaffold-plan.md` — 11 user-approved decisions (Vite 8, React 19, Tailwind v4, local shadcn, magicui MCP, tremor, motion, dist-directory serving), directory tree, build/serve contract, **preservation contract** §5a sidebar / §5b total-token hero, 4 phases, risks.
- **`src/claudey/api/admin_static/admin-ui/` — Vite 8 + React 19 + TS + Tailwind v4 scaffold:**
  - `tokens.css` + `globals.css` — full design-token theme mapped into Tailwind v4 `@theme` (heat, surfaces, text, hairlines, radius, elevation, motion keyframes; reduced-motion global).
  - `lib/utils.ts` (cn/compactNumber/thousands/formatUsd/formatIdr), `api/client.ts` + `api/types.ts` (typed fetchers for `/admin/api/usage|dashboard`), `hooks/use-reduced-motion.ts`, `hooks/use-stored-flag` (in use-reduced-motion.ts), `hooks/use-count-up.ts`, `hooks/use-json.ts`.
  - **Preserved Sidebar** (`shared/layout/sidebar.tsx`) — exact choreography port: rAF per-frame easeOutQuint width tween, collapse 350ms / expand 220ms, label fade ends 120px / budget fade 170px, nav pill glide easeOutQuart 160ms with travel-anchored sine dip `PILL_DIP=0.07`, retarget-safe, snap under reduced-motion / ≤900px, `claudey.sidebar.collapsed` persistence, `aria-expanded`/`aria-hidden`, brand-mark hover `rotate(-4deg) scale(1.05)`.
  - **Preserved UsageHero** (`app/usage/usage-hero.tsx`) — 8 concentric ripple rings (`size=140+i*70`, `opacity=max(0.08,0.4-i*0.045)`, delay `i*0.06s`, 3.2s `cubic-bezier(0.4,0,0.2,1)` scale 1→0.78→1, mask fade), sliding period pill (Total/24h/7d/30d), count-up (500ms easeOutCubic), compact⇄full toggle, cost row (USD + IDR).
  - `shared/layout/sidebar-budget.tsx` — budget widget fed by `/admin/api/dashboard`, fade driven by sidebar tween's `--sidebar-budget-opacity`.
  - `app/usage/usage-view.tsx` — live container (loading/empty/error states with personality), provider breakdown strip.
  - `app/views/placeholder-view.tsx` — design-system scaffold states for providers/model_config/messaging.
  - `app.tsx` + `main.tsx` — app shell: sidebar + topbar + view switch + theme toggle + `#hash` deep links.
  - `components/ui/shadcn/button.tsx` — five Apple grammars as CVA variants with heat substituted.
- **Serving integration (decision #11, dist-directory serving):**
  - `build.mjs` copies Vite `dist/` → committed `admin_ui_dist/` (offline-safe, no CDN).
  - `vite.config.ts` `base: "/admin/ui/"` — absolute hashed asset URLs.
  - `admin_routes.py` — new `GET /admin/ui` (entry, loopback-guarded) + `GET /admin/ui/assets/{filename}` (traversal-safe) serving `admin_ui_dist/`; vanilla `/admin` untouched.
- **Tests (`tests/api/test_admin.py`):** 6 new tests — entry served, loopback-only, assets served (regex-derived hashed name), unknown/traversal 404s.

## What Changed This Iteration

- Fixed: `useStoredFlag` re-written to `useState` (previous `useSyncExternalStore` never notified); removed unused imports to satisfy `noUnusedLocals`.
- Added: `.npmrc` `legacy-peer-deps=true` (tremor 3.18.7 declares peer `react@^18`, React-19-safe in practice).
- Added: `.gitignore` entry for `admin-ui/dist/` (intermediate build output; `admin_ui_dist` is the committed serving dir).
- CI unblocks (pre-existing branch drift, zero-risk convention fixes):
  - `scripts/fetch_provider_logos.py` — added `None` letter-chip fallback mappings for `llm7, novita, ovhcloud, qwen, routeway, scaleway` (same convention as `wafer`/`pecut`) + regenerated the 6 fallback SVGs; reverted accidental overwrite of 5 hand-crafted committed logos (anthropic heat mark, real pecut vector).
  - `src/claudey/core/secret_crypto.py` — removed banned `from __future__ import annotations` (ty + 14 tests green).
- Bumped scout logo-count test `34 → 40` (6 new fallback chips; kept in sync with the logos script).

## Known Issues

- **Pre-existing CI failures (NOT from this scaffold — verified by stash: fail on pristine branch HEAD):**
  1. `tests/contracts/test_import_boundaries.py::test_package_dependencies_follow_declarative_policy` — 9 undeclared cross-package import edges introduced by the phase-a providers work, e.g. `application/failover → providers.health`, `config/custom_provider_check → providers.{anthropic.messages, openai_chat.base_url}`, `config/custom_providers → core.secret_crypto`. Fix = phase-a owner reconciles `ALLOWED_PACKAGE_DEPENDENCIES` or refactors to owned facades. Deliberately NOT policy-hacked here.
  2. `test_import_boundaries.py::test_external_consumers_use_owned_package_facades` — same root cause (`custom_provider_check` reaching into `providers.openai_chat.base_url`).
  3. `tests/runtime/test_provider_manager.py::test_catalog_publication_tracks_warm_refresh_and_direct_cache` — expected warm-refresh set not updated after the 6 new catalog providers gained models (`ovhcloud/warm-model`, `llm7/warm-model` now published). Needs phase-a confirmation that cross-provider warm publication is intended before updating the expectation.
  - One observed flake: `test_generated_catalog_schema_is_accepted_by_installed_codex` failed once during full CI, passes in isolation (not related to changes).
- React app is served at `/admin/ui`; `/admin` still serves the vanilla app until Phase 3 views reach parity and Phase 4 sunsets vanilla (plan §6/§9).
- Tremor recharts@2 deprecation warning at install (transitive; charts ship Phase 3).

## Dev Server

- URL: http://127.0.0.1:8090/admin (vanilla) and http://127.0.0.1:8090/admin/ui (React scaffold)
- Status: running (restarted this iteration to load `/admin/ui` routes)
- Command: `uv run hans-server` (background, log at `/tmp/claudey-admin-server.log`)
- Build: `cd src/claudey/api/admin_static/admin-ui && npm run build` → copies to `admin_ui_dist`
