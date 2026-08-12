# Generator State — Phase 4 Sunset (React at /admin)

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

- Phase 4 serving migration completed (React now IS /admin; vanilla retired).
- Fixed the 2 failing tests:
  - `test_admin_responses_are_never_cached` — asset paths now resolved before
    `_set_home` chdirs into tmp_path.
  - `test_admin_api_fetches_bypass_browser_cache` — the Vite minifier emits the
    `no-store` directive as a backtick template literal, so the assertion now
    matches any quote style.
- Restarted the dev server; verified `/admin` → 200 (React), `/admin/ui` → 308,
  `/admin/assets/index-CSI3R7ZS.js` → 200.
- Full CI: 3 failed / 3109 passed — the 3 failures are the pre-existing,
  unrelated ones (import boundaries ×2, provider_manager warm-refresh ×1).

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