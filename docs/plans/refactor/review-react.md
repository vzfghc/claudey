# React Review — admin-ui micro-frontend

Reviewed: `src/claudey/api/admin_static/admin-ui` (React 19 + Vite + TS 5.8 + Tailwind 4)
Rev: `7ce75363` (repo) — standalone Vite SPA, not Next.js, so RSC/server-client boundary rules do _not_ apply.

Gates:
- `npm run typecheck` — PASS (exit 0, no errors)
- `npm run lint` — NOT CONFIGURED (no eslint dep; no eslint-plugin-react-hooks/jsx-a11y) — HIGH config gap
- Build — admin_ui_dist is a committed hashed build

## Summary
- CRITICAL: 0
- HIGH: 1 (config gap: React lint rules not enforced)
- MEDIUM: 4
- LOW: 2

## CRITICAL
None. Audit of React-security lanes:
- No `dangerouslySetInnerHTML` on user data. The only occurrence is the stock shadcn
  `ChartStyle` (`chart.tsx:82`) which interpolates developer-supplied chart `id`/theme hex
  values into a CSS `<style>` block — no user input path, no XSS vector. Note only.
- No `javascript:`/`data:` hrefs. `bar-list.tsx:127` has `rel="noreferrer"` (implies noopener).
- No secrets in the client bundle: the SPA reads no env vars at all; all data comes from
  loopback-only `/admin/api/*`.
- `localStorage` used only for the theme preference (`main.tsx:9`), wrapped in try/catch — not a token.

## HIGH
[HIGH] eslint-plugin-react-hooks / jsx-a11y not configured
File: admin-ui/package.json (no eslint dep, no lint script)
Issue: The project has no ESLint, so `react-hooks/rules-of-hooks`, `react-hooks/exhaustive-deps`,
and `jsx-a11y` are never enforced; the typecheck-only gate cannot catch hook violations or a11y regressions.
Why: Hook misuse and a11y regressions silently pass CI.
Fix: Add eslint + eslint-plugin-react-hooks + eslint-plugin-jsx-a11y (or eslint-plugin-react-compiler)
with the required rules as "error", and wire `npm run lint` and `npm run typecheck` into CI.

## MEDIUM
[MEDIUM] `key={index}` on a removable/mutable fallback chain
File: src/components/app/providers/combo-dialog.tsx:153
Issue: `nodes.map((node, index) => <div key={index}>` — a fallback chain the user edits via
`addNode`/`removeNode`. Removing an interior node shifts indices, so React reuses the wrong row
instance. `ComboNode` has no stable id.
Why: `ComboNode` has no stable identifier, so the combobox's transient open/dropdown state can
attach to the wrong row after a delete.
Fix: Give each node a stable id (e.g. an incrementing counter or `crypto.randomUUID()` in
`emptyNode()`), keep it when copying, and use `key={node.id}`.

[MEDIUM] tablist signals ARIA tabs but lacks arrow-key nav and panel pairing
File: src/components/app/usage/usage-hero.tsx:93-124
Issue: `role="tablist"` + `role="tab"` + `aria-selected` are present, but no `onKeyDown` for
Left/Right/Home/End, and no `aria-controls` / `role="tabpanel"` / `aria-labelledby` to a panel.
Why: The tablist marks a navigational pattern AT users expect; directional keys are not implemented
and the selected tab is not linked to its panel.
Fix: Add the directional key handler (roving tabindex or focus the active tab on Arrow keys) and
pair each tab to its panel with `aria-controls`/`tabpanel`/`aria-labelledby`; or drop the tab roles
and rely on the plain buttons.

[MEDIUM] Config editor has no semantic `<form>`
File: src/components/app/views/model-config-view.tsx, src/components/shared/form/config-action-bar.tsx
Issue: Config Save/Apply is a `<Button onClick={apply}>` with no enclosing `<form>`, `onSubmit`, or
`preventDefault`.
Why: Loses native submit-on-Enter and the form/section accessibility mapping the fieldset pattern
gives.
Fix: Wrap in a `<form onSubmit={(e) => { e.preventDefault(); void apply(); }}>` and type the Save
button `type="submit"`.

[MEDIUM] Config fetch races / no abort on refresh
File: src/hooks/use-config-form.ts:28-95
Issue: `load()` and `refresh()` call `fetchConfig`/`fetchModels` without an AbortController; two
rapid `refresh()` or reloads can resolve out of order, and an in-flight response may set state
after unmount.
Why: A slow earlier request can overwrite a faster newer one with stale payload (minor, admin UI).
Fix: Track an in-flight controller in a ref and abort it at the top of `load`/`refresh`; cleanup on
unmount.

## LOW
[LOW] `chart.tsx:82` interpolates chart id/config into injected CSS without sanitization
Issue: shadcn `ChartStyle` builds `[data-chart=${id}]` CSS from props. Safe today (id is a
developer constant) but if `id` is ever derived from server data this becomes CSS injection.
Fix: Validate `id` against `[a-zA-Z0-9_-]` before interpolation.

[LOW] Mouse-first copy on a toggle button
File: src/components/app/usage/usage-hero.tsx:127-135
Issue: `title="Click to toggle between compact and full numbers"` uses "Click" and the pattern is a
press-toggle (`aria-pressed`), which is keyboard-ok but copy is mouse-centric.
Fix: Rephrase to "Toggle between compact and full numbers"; keep `aria-pressed`.

## Verified clean
- `api/client.ts`: typed wrapper, no `any`, no secrets, loopback-only endpoints, consistent `detail`
  error shape, `no-store` cache.
- `main.tsx`: `createRoot` + StrictMode (React 19 correct); theme read is guarded and non-sensitive.
- Hooks: `useConfigForm` uses `useCallback`/functional updaters correctly; derived `dirtyCount`
  computed during render (no effect-for-derived-state).
- Keys: `usage-hero.tsx:77/79` (fixed decorative rings) and `providers-view.tsx:39` /
  `placeholder-view.tsx:75` (static skeletons/placeholders) are acceptable index uses.
- Decorative `aria-hidden` and labeled interactive controls are handled well.

## Resolution (2026-08-15)

All findings addressed. Gates after fixes: `npm run lint` (0 errors), `npm run typecheck`
(0 errors), `npm run build` (success, `admin_ui_dist/` regenerated).

### HIGH — ESLint / react-hooks / jsx-a11y not configured — FIXED
Added flat-config ESLint 9 stack (`eslint`, `typescript-eslint`, `eslint-plugin-react-hooks`,
`eslint-plugin-jsx-a11y`, `@eslint/js`, `globals`) in `eslint.config.js`, with
`react-hooks/rules-of-hooks` and `react-hooks/exhaustive-deps` as **error**; added the
`npm run lint` script. A `config-protection` hook blocks weakening `eslint.config.js`, so every
violation below was fixed in source, not silenced.

Enabling the linter surfaced 9 real violations (beyond the original review), all fixed:
- `shared/layout/sidebar.tsx` — 2× `react-hooks/exhaustive-deps`: wrapped the `hoverPillState` /
  `activePillState` ref-bundles in `useMemo` (stable identity over the underlying refs) and added
  them to the `hoverGlide` `useCallback` and the active-pill `useLayoutEffect` dep arrays.
- `app/config/model-combobox.tsx` — `role-has-required-aria-props` + `interactive-supports-focus`:
  completed the ARIA combobox pattern — `useId`-based `aria-controls` → listbox `id`,
  `aria-activedescendant` → active option `id`, per-option `id`, and `tabIndex={-1}` on options
  (managed-focus composite widget; focus stays on the input).
- `app/providers/provider-key-dialog.tsx` — `no-autofocus`: removed the redundant `autoFocus`
  (Radix `Dialog.Content` already focus-traps to the first focusable element on open).
- `app/providers/combo-dialog.tsx` — 2× `label-has-associated-control`: wired `htmlFor`/`id`
  between each `<label>` and its Radix `Checkbox` (per-row `${node._key}-enabled`, and
  `combo-enabled`). Also fixed a `no-unused-vars` in `stripNodeKey`.

### MEDIUM/LOW — all 6 code findings FIXED
- `combo-dialog.tsx` — `key={index}` → stable `key={node._key}`. Rows carry a client-only `_key`
  (incrementing counter) via `emptyNode()`/`toNodeRow()`; `stripNodeKey()` removes it before any
  API payload (validate/save).
- `usage-hero.tsx` — tablist keyboard nav implemented as **roving tabindex**: `onKeyDown`
  (Left/Right/Home/End) lives on each tab `<button>` (focusable), active tab `tabIndex={0}` /
  others `-1`; tabs paired to a `role="tabpanel"` via `aria-controls`/`aria-labelledby`. Toggle
  copy reworded "Click to toggle…" → "Toggle…" (LOW).
- `model-config-view.tsx` + `config-action-bar.tsx` — Config editor wrapped in
  `<form onSubmit={e => { e.preventDefault(); void handleApply(); }}>`; Save button `type="submit"`
  (restores submit-on-Enter).
- `use-config-form.ts` — `load()`/`refresh()` track an in-flight `AbortController` in a ref, abort
  the prior request at entry, guard state-sets on `signal.aborted`, and abort on unmount.
- `chart.tsx` — `ChartStyle` validates `id` against `SAFE_CSS_ID` (`/^[a-zA-Z0-9_-]+$/`) before
  interpolating into the injected `<style>`; returns `null` on mismatch (LOW, defense-in-depth).

### Residual
- ESLint runs locally via `npm run lint` only; not yet wired into the Python CI
  (`scripts/ci.sh` / `tests.yml`).
- These are production files under `src/claudey/api/`; a `pyproject.toml` semver bump is required
  before this lands on `main`.
