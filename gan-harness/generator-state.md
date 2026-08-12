# Generator State — Phase-A Refactor Sprint 0 (import-boundary contract green)

> Track: refactor foundation sprints (docs/plans/refactor/REFACTOR_PLAN.md).
> Branch: `feat/phase-a-free-providers` · HEAD `0db4fb43`.
> Status: Sprint 0 iteration 1 complete — boundary test 21/21 green.

## Sprint 0 (iteration 001) — What Was Built

- C1: `core/anthropic/urls.py` owns `ANTHROPIC_VERSION_HEADER`,
  `anthropic_messages_url`, `openai_v1_base_url`; all src importers repointed
  (config/custom_provider_check.py, providers/anthropic/messages.py,
  openai_chat facade + profiles); `providers/openai_chat/base_url.py` deleted
  (zero importers, complete migration).
- C2: `providers/health.py` → `application/health.py` (git mv) + test moved to
  `tests/application/test_health.py`; 3 remaining import sites updated.
- C3: sanctioned contract amendment `config: {"core"}` in
  test_import_boundaries.py + ARCHITECTURE.md policy table.
- Verification: boundary 21 passed; ty clean; ruff clean; targeted 192 passed;
  providers suite 937 passed; coverage 90% (= baseline 90%).
- Report: `docs/plans/refactor/sprint-report-0-001.md`.
- Known: pre-existing `test_catalog_publication_tracks_warm_refresh_and_direct_cache`
  failure unchanged from baseline (verified via stash); untracked root junk
  untouched (Sprint 8 scope).

---

# (Superseded) Generator State — Phase 4 Sunset (React at /admin)

> Track: React micro-frontend (docs/design-system.md + docs/frontend-scaffold-plan.md).
> Branch: `feat/phase-a-free-providers` · HEAD `a6c3b152`.
> Status: Phase 4 (retire vanilla admin + move React to /admin) implemented.

## What Was Built

- **Serving migration** (`admin_routes.py`):
  - `GET /admin` serves the built React entry (`admin_ui_dist/index.html`).
  - `GET /admin/ui` 308-redirects to `/admin` (legacy path).
  - `GET /admin/assets/{filename}` serves hashed Vite chunks — traversal-safe
    (resolve + `root in parents` check), loopback-only.
  - Removed the vanilla allowlist (`admin.css/js`, `admin-animations.css/js`,
    `beam.bundle.js`) and the old `_asset_response` helper.
  - `GET /admin/assets/logos/{filename}` unchanged (provider logos).
- **Vanilla admin deleted** — `admin.css`, `admin.js`, `admin-animations.css`, `admin-animations.js`, `beam.bundle.js`, `index.html` all removed from `admin_static/`.
- **vite.config.ts**: `base` changed `/admin/ui/` → `/admin/` so emitted asset
  URLs are absolute against `/admin`.
- **Test suite rewritten** (`tests/api/test_admin.py`, 95 tests):
  - `/admin` entry serves React (`id="root"`), no-store.
  - `/admin/ui` → 308 `/admin`; loopback-only both ways.
  - `/admin/assets` serves hashed chunks; rejects unknown + traversal.
  - `no-store` enforced on all admin responses (good + error paths).
  - React bundle carries the `cache: no-store` fetch directive (minifier-safe
    regex) and the `_fallback.svg` custom-provider logo markers.
  - Removed ~27 obsolete vanilla-static tests (beam, OAuth preopen, vanilla
    markup, static file serving).

## What Changed This Iteration

### GAN Harness Iteration 003 — Evaluator + Generator

- **Evaluator**: Wrote `gan-harness/feedback/feedback-003.md` scoring 5.6/10 (FAIL).
  - 2 critical bugs identified: `useConfigForm` never calls `load()` on mount
    (Model Config + Messaging stuck on syncing skeleton), `UsageTrendChart` passes
    raw hex to tremor `colors` prop (chart fill invisible).
  - 2 major issues, 2 minor issues documented.
- **Generator**: Fixed both critical bugs:
  1. `src/claudey/api/admin_static/admin-ui/src/hooks/use-config-form.ts` — added
     `useEffect(() => { void load(); }, [load])` to trigger initial fetch on mount.
     Also imported `useEffect` from react.
  2. `src/claudey/api/admin_static/admin-ui/src/components/app/usage/usage-trend-chart.tsx` —
     changed `colors={["#ff4d00"]}` to `colors={["orange"]}` (tremor palette color).
- **Verification**: React build succeeded, typecheck passed, all 95 admin tests
  passed, Playwright confirmed all 4 views load real data. Screenshot confirms
  usage chart fill visible with tremor orange color.
- Remaining non-blocking issues from feedback-003 deferred: y-axis tick spacing,
  empty combos button placement, sidebar nav hash sync, favicon 404.

## Known Issues

- 3 pre-existing CI failures remain (import boundaries ×2, provider_manager
  warm-refresh ×1) — unrelated to this phase.
- Phase 4 §13 (a11y / reduced-motion / contrast) and §15 (add admin-ui build to
  CI gate) still open.
- Connected-account OAuth flow not ported to React (vanilla tests removed, not
  migrated — OAuth isn't in the bundle yet).
- On `main`, `admin_routes.py` is a production file → needs a semver bump in
  `pyproject.toml` + `uv lock` alongside the commit (not done on this feature
  branch).

## Dev Server

- URL: http://127.0.0.1:8090/admin (React app, replaces vanilla)
- /admin/ui → 308 redirect to /admin
- Status: running (restarted after route change)
- Command: `uv run hans-server` (background, log at `/tmp/claudey-admin-server.log`)
- Build: `cd src/claudey/api/admin_static/admin-ui && npm run build` → copies to `admin_ui_dist`
- Typecheck: `npm run typecheck` — passes clean