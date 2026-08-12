# Evaluation Rubric: Claudey Admin UI (React micro-frontend)

> Consumed by the Evaluator agent. Contract spec: `gan-harness/spec.md`. Reference: `docs/design-system.md` (authoritative tokens). Live app: **http://127.0.0.1:8090/admin** (dev server running; React app, vanilla retired).
> Score each category 0–10, apply weights, sum. **Pass: weighted ≥ 7.0 AND no axis < 5 AND all hard gates pass.** Otherwise iterate: write evidence + prioritized fix list to `gan-harness/feedback/feedback-NNN.md` (increment N; next is **feedback-003.md**).

## 0. Hard Gate — Blockers (any fail ⇒ overall 0)

- [ ] React admin app serves at **http://127.0.0.1:8090/admin** — entry HTML has `id="root"` and loads `/admin/assets/index-*.js`; `/admin/ui` 308-redirects to `/admin`. Page loads with **zero console errors** (collect `page.on("console")` + `page.on("pageerror")`; pageerror ⇒ fail).
- [ ] No broken assets: every `<script>`, `<link>`, `<img>` referenced by the served HTML loads 200 (loopback-only, so hit them from 127.0.0.1).
- [ ] All four views (Providers, Model Config, Messaging, Usage) render **real content** — none stuck on a perpetual loading skeleton. (Top known concern.)
- [ ] Design-system.md compliance: heat `#ff4d00` is the single interactive accent; no Apple Action Blue `#0066cc`, no Firecrawl `#fa5d19`; semantic colors (success/warn/danger/info) are never interactive chrome; body copy 17px (not 16px); no weight 500 (ladder 300/400/600/700); no decorative gradients/shadows on cards; token refs (Tailwind theme vars) not inline hex in components.
- [ ] Preserved **Sidebar** and **UsageHero** are not redesigned (sidebar easeOutQuint tween + nav-pill breathing glide; hero ripple rings + count-up intact).
- [ ] `./scripts/ci.sh` passes. (NOTE: exactly 3 known pre-existing Python failures are unrelated to the UI and acceptable: `tests/contracts/test_import_boundaries.py` ×2 and `tests/runtime/test_provider_manager.py::test_catalog_publication_tracks_warm_refresh_and_direct_cache`. Any React/UI-related failure is a blocker.)

## Eval Hygiene (mandatory, before scoring)

1. Isolate: `context.addInitScript(() => localStorage.clear())` on a fresh context.
2. Do NOT trigger a destructive Apply/Restart against the real server (Apply may restart the server and kill the eval session). Test hover/press via `locator.hover()` / `page.mouse.down()` without `mouse.up()`, or just assert controls render + are enabled.
3. After dirtying a field for state tests, reload the view so no committed state leaks.
4. Screenshot each view at 1440px, and the Usage charts at 375px (overflow check).

## 1. Design Quality (weight 0.3)

- Token-faithful: surfaces canvas `#ffffff` / parchment `#f5f5f7`; text ink `#1d1d1f` / ink-muted-48 `#7a7a7a`; hairline `#e0e0e0`; radius grammar (xs5/sm8/md11/lg18/pill) respected and not mixed.
- Typography per Apple grammar: 34px/600/`-0.374px` display heads, 17px body, `tabular-nums` on numbers, mono for keys/tokens, no weight 500.
- Heat `#ff4d00` (or heat-soft/alpha) for all interactive signals; pill radius for actions.
- No AI-slop: no purple/blue gradients, no stock layouts, no decorative shadows on cards/buttons.

## 2. Originality (weight 0.2)

- Reads as "claudey" (Apple × Firecrawl merge, heat brand), not a default shadcn/tremor theme.
- Preserved Sidebar + UsageHero give distinctive identity; the four views extend it rather than copying a template.

## 3. Craft (weight 0.3)

- Loading / empty / error / success states exist and are polished (skeleton → content; sensible empty states; error states with a Retry action).
- Charts render correctly: Usage trend area chart has a visible heat-colored fill with sane axes (tremor `colors` must be a valid palette color, not a raw hex — raw hex is a known bug); heatmap cells align with month/day labels; provider stacked bar + per-provider bars proportional to token share.
- Interactions: buttons hover/active states, sonner toasts on actions, no layout shift, no 375px overflow.
- Config form: editing a field marks it dirty (action bar dirty count); Validate/Apply/Restart wired; Model Config role cards + Web Tools + Messaging voice section render their fields.

## 4. Functionality (weight 0.2)

- **Model Config view loads real data** (not a stuck skeleton) — Fallback/Fable/Opus/Sonnet/Haiku role cards + Web Tools fields render from `/admin/api/config`.
- **Messaging view loads real data** — Messaging + Voice notes sections render from `/admin/api/config`.
- **Providers view** renders provider grid (status badges), custom-provider dialog, combo cards/dialog.
- **Usage view** renders hero + ProviderBreakdown + heatmap + trend chart + daily table with real data; Refresh works.
- Empty/error states behave (no usage log → empty state, not a crash).

## Screenshots to capture
`initial-load`, `providers`, `model-config` (must show FIELDS, not skeleton), `messaging` (must show FIELDS, not skeleton), `usage` (full + zoom on trend chart), `usage-mobile-375`, `providers-empty`.