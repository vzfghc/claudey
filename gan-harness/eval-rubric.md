# Evaluation Rubric: Firecrawl Animation Patterns in the Claudey Admin

> Consumed by the Evaluator agent. Contract spec: `gan-harness/spec.md` (six features, exact values, acceptance criteria). Reference: `docs/firecrawl-animation-reference.md`.
> Score each category 0–10, apply weights, sum. **Pass: weighted ≥ 8.0 AND no axis < 5 AND all hard gates pass.** Otherwise iterate: write evidence + prioritized fix list to `gan-harness/feedback/feedback-NNN.md` (increment N).

## 0. Hard Gate — Blockers (any fail ⇒ overall 0)

- [ ] Admin UI serves at http://127.0.0.1:8082/admin (or the port recorded in `gan-harness/generator-state.md`); page loads with **zero console errors** (collect `page.on("console")` + `page.on("pageerror")`; pageerror ⇒ fail).
- [ ] `./scripts/ci.sh` passes (ruff format, ruff check, ty, pytest) on the generator's tree.
- [ ] `pyproject.toml` version is `5.10.0` (MINOR bump, new capability) and `uv.lock` is in sync (`uv lock` ran in the same commit); production files under `src/claudey/api/` committed with the bump.
- [ ] No broken assets: every `<img>`, `<link>`, `<script>` in the served page resolves 200; logos directory list and marquee img srcs match 1:1 (no fabricated slugs).
- [ ] Accessibility attributes intact: `#sidebarToggle` has `aria-expanded` (flips on toggle), `aria-controls="sectionNav"`, `aria-label`, `title`; `#toastContainer` has `aria-live="polite"`; toasts have `role="status"`; `#sectionNav` has `aria-label="Admin views"`.
- [ ] New static-assertion tests exist in `tests/api/test_admin.py` (repo convention `test_admin_static_*`) covering the new files and pass in CI.

## Eval Hygiene (mandatory, before scoring)

1. Isolate: `context.addInitScript(() => localStorage.clear())` on a fresh context; do NOT rely on prior generator runs' localStorage state.
2. Never click `#applyButton`'s full press or `#restartButton` against a real server — `Apply` may restart the server and kill the eval session. For `:active` testing use `locator.hover()` for hover states, and for press states dispatch `pointerdown` via `page.mouse.down()` on the button's center **without** `mouse.up()`, then `mouse.up()` on a neutral area.
3. After dirtying a form field for button-state tests, restore it or reload the page so no uncommitted state leaks into later checks.
4. Measure with per-frame samplers injected via `page.evaluate` (`setInterval` at ~8–12ms, sampling `getComputedStyle`), not screenshots. For transform parsing, decompose the `matrix(...)` string.
5. For reduced-motion checks use `page.emulateMedia({ reducedMotion: 'reduce' })` then reload before asserting.
6. Record measured numbers in evidence; do not assert "smooth" without a sampled series.

---

## 1. Animation Fidelity (weight 0.30)

### 1.1 Sidebar tween (Feature 1) — score the collapse AND expand

- [ ] Collapse: click `#sidebarToggle`; sample `aside.sidebar` width via injected interval. PASS band: ≥ 10 distinct sampled widths strictly between 64 and 256; total tween duration 250–500ms; width at t≈100ms < 160px (snappy start); first sample after click is already < 256.
- [ ] Mechanism: mid-tween `sidebar.style.width` is a non-empty inline value (e.g. `"188.45px"`), not set via CSS class alone. `getComputedStyle(sidebar).transitionProperty` does NOT contain `width` (no CSS width transition).
- [ ] Easing: late-collapse samples (t ≈ 80–90%) are closer to 64px than linear extrapolation (gentle settle); no visible stall at start.
- [ ] Labels: `.brand-text` and at least one `.nav-label` computed `opacity` is strictly between 0 and 1 at a mid-collapse sample, and 0 at end of collapse; both are non-empty and visible again after expand.
- [ ] Rail state: after collapse completes, `document.body.classList` contains `sidebar-rail`; nav-link icons centered (nav-link `justify-content: center`, padding `10px 0`); `--sidebar-w` var on `<html>` is `64px`; `.action-bar` computed `left` ≈ 64px.
- [ ] Expand: click again; tween duration 150–350ms; ≥ 5 distinct intermediate widths; ends at 256px; inline width style cleared (`sidebar.style.width === ""`) after settle; `.action-bar` left ≈ 256px.
- [ ] Rapid double-click: two clicks 120ms apart do not leave the sidebar stuck mid-width (it finishes in a valid end state).
- [ ] aria: `aria-expanded` flips to `"false"` at click time (before tween completes) and back to `"true"` on expand; `title`/`aria-label` flip.

### 1.2 Nav pills (Feature 2)

- [ ] Structure at ≥901px: exactly one `.nav-pill-active` and one `.nav-pill-hover` inside `#sectionNav`, both `aria-hidden="true"`, `pointer-events: none`.
- [ ] Pitch: active pill `transform` translateY = 46px × index (measured: index 1 ⇒ 46px ± 2px; index 2 ⇒ 92px ± 2px).
- [ ] Click 2nd nav link: ≥ 2 distinct sampled translateY values strictly between 0 and 46 during the glide; settles ≤ 300ms; final computed `background-color` of `.nav-pill-active` is heat-tinted (`rgba(250,93,25,0.10)`-family, dark theme allowed darker); `.nav-link.active` computed background is `transparent`; `aria-current="page"` moved to the new link.
- [ ] Hover: hovering 2nd link ⇒ `.nav-pill-hover` opacity ≈ 1 with translateY ≈ 46px; leaving the nav ⇒ opacity 0.
- [ ] Initial load: no pill slide animation on first paint (`nav-pills-ready` gating — sample transform at load: already at index 0).
- [ ] ≤900px: zero pills in DOM (or display:none); per-item `.nav-link.active` highlight still visible (moved rules).

### 1.3 Lift-and-press buttons (Feature 3)

- [ ] `#validateButton` (secondary): computed `box-shadow` contains `inset 0 -6px 12px` and an ambient `0 2px 4px` layer; hover (Playwright `hover()`) changes ambient to `0 4px 8px` (blur 4→8).
- [ ] Sheen: `getComputedStyle(btn, "::before").opacity` ≈ 0.06 at rest, ≈ 0.08 on hover.
- [ ] Press: dirty a field so `#applyButton` enables; `mouse.down()` on its center (no up): within ~100ms computed `transform` ≈ scale(0.995) (matrix scale 0.995 ± 0.004), `::before` opacity → 0, box-shadow contracted (no `4px 8px` ambient layer). Release on neutral area.
- [ ] Disabled `#applyButton` (fresh load): `box-shadow: none`, `::before` opacity 0.
- [ ] Ghost buttons (`.ghost-button`): no layered shadows (regression flat).

### 1.4 Sonner-style toasts (Feature 4)

- [ ] Enter: trigger a toast (e.g. via safe validate `Ctrl+S`); sampler within first 250ms finds computed scale < 0.85 that settles to 1; opacity goes 0→1.
- [ ] Click-dismiss: clicking a toast adds `.toast-leaving`; element removed from DOM ≤ 400ms after click.
- [ ] Swipe-dismiss: `mouse.down()` on toast center, move +120px in ~5 steps, sample mid-drag (translateX ≈ 120, opacity < 1), `mouse.up()`: toast removed from DOM ≤ 400ms after release.
- [ ] Snap-back: drag +40px then release: transform returns to `none` within ~350ms and toast STAYS in DOM (auto-dismiss timer notwithstanding — run this check within the 4s window).
- [ ] Loading toast: in Model Config view click refresh-models button: `.toast-loading` appears with a spinning icon (rotating transform samples over 100ms differ); it does NOT auto-dismiss within 2s; completes into an ok/warn toast.
- [ ] `#toastContainer` retains `aria-live="polite"`.

### 1.5 Logo marquee (Feature 5)

- [ ] Structure: `.provider-marquee` exists as first child of `#view-providers`; two `.marquee-track` divs; each contains 64 `<img>` (32 slugs × 2); all `src` match `/admin/assets/logos/<slug>.svg` from the real directory listing; zero broken images (`naturalWidth === 0` count = 0).
- [ ] Motion: sample `transform` of track A twice, 500ms apart: |Δx| ≈ 16px (10–22px band, 32px/s); x decreasing (scroll left); track B Δx is positive and ≈ equal magnitude (mirrored).
- [ ] Hover pause: hover `.marquee`; transform stable (|Δx| < 2px) over 400ms.
- [ ] `aria-hidden="true"` on `.marquee`; caption `All supported providers` is the accessible label.

### 1.6 Reduced motion (Feature 6)

- [ ] `page.emulateMedia({ reducedMotion: 'reduce' })` + reload: click `#sidebarToggle` — sampler finds ≤ 3 distinct sampled widths with NO value strictly between 100 and 200 (instant jump); expand likewise.
- [ ] Marquee static: track transforms identical (|Δx| < 2px) over 600ms; no rAF loop (check via a module-exposed flag if present, else transform stability).
- [ ] Toasts: enter/exit have no scale animation (opacity-only change or instant).

---

## 2. Design (weight 0.25)

- [ ] Pill system reads as one gliding indicator (firecrawl §4.3), not per-item boxes: at ≥901px `.nav-link.active` and `.nav-link:hover` computed backgrounds are transparent (verified in 1.2); heat tint lives on the shared pill only.
- [ ] Sidebar rail at 64px: icons vertically centered per item, no clipped text at any intermediate width (labels fade before clipping), chevron press feedback exists (`:active` scale on `#sidebarToggle`).
- [ ] Buttons look physical: inset bottom glow visible on both primary and secondary at rest; sheen is subtle (0.06, not a white wash); hover lift perceptible; press sinks (0.995 scale) without layout shift (overflow hidden, no reflow).
- [ ] Marquee: masked edges (gradient mask), caption typography consistent with existing mono section labels, logos at 32px with consistent opacity; no layout jump when images load.
- [ ] Toasts: scale-fade enter is sonner-like; loading spinner matches the accent; toast stack still aligned (`.toast-container` positioning unchanged).
- [ ] Cohesion: no new hues, no gradients beyond sheen/mask, no emoji, no new fonts; dark theme (`prefers-color-scheme`) still coherent (pills, sheen, marquee adapt).
- [ ] Anti-slop audit: no CSS `transition: width`/`left` on sidebar or action-bar; no `::before` nav indicator bars at ≥901px; no unconditional keyframe animations outside `prefers-reduced-motion` gate (grep the new CSS/JS).

## 3. Craft (weight 0.25)

- [ ] File organization per spec: `admin-animations.css` (~300 lines) and `admin-animations.js` (~380 lines) both < 800 lines; `admin.js`/`admin.css` surgical edits only (no wholesale rewrites); index.html gains exactly the 2 asset links + marquee markup.
- [ ] No dead code: no unused constants/functions in the new module; no leftover duplicate rules (e.g. old `.toast-in` keyframe removed or superseded cleanly).
- [ ] Immutability/no-mutation: module never rewrites existing handlers or mutates `admin.js` state objects; all DOM additions are new nodes; `window.__sidebarTweenToggle` fallback pattern keeps `admin.js` functional standalone (verify: with the module blocked, sidebar toggle still collapses via class).
- [ ] Error handling: missing logo imgs hidden gracefully; tween guards against null nodes (`querySelector` results checked); `matchMedia` change listeners cancel loops (no orphaned rAF).
- [ ] Edge cases: double-click mid-tween reverses from current width; resize across 900px snaps to valid state; localStorage-preserved collapsed state loads instantly (no flash); marquee hidden when not on Providers view (parent view hides it).
- [ ] Tests: `test_admin_static_*` assertions cover the six features' key contract strings (e.g. `--sidebar-w`, `nav-pill-active`, `sonner-in`, marquee slug count, `__sidebarTweenToggle`, `prefers-reduced-motion` handling).
- [ ] No `console.log` in shipped files (grep); no `# type: ignore` in any touched Python.
- [ ] Comments concise; constants named (no magic numbers: durations/easings/pitches are named constants in the module).

## 4. Functionality (weight 0.20)

Regression: every pre-existing flow must still work.

- [ ] Config loads: provider cards render with logos; server status pill shows correct state; welcome greeting + pageTitle correct.
- [ ] View switching: clicking each nav link shows the right `#view-*` section (hidden toggling), updates `#pageTitle`, moves `aria-current`, and glides the active pill.
- [ ] Dirty state: editing a field flips `#dirtyState`, enables `#applyButton`; reloading restores server config (no persisted corruption from eval).
- [ ] Keyboard: `Cmd/Ctrl+S` triggers validate (safe); `Cmd/Ctrl+Enter` disabled when clean; focus-visible outlines visible on buttons/links (tab through).
- [ ] Mobile: viewport 800×900 — sidebar shows as mobile drawer; `#sectionNav` `inert` honored when collapsed on mobile; nav links ≥ 44px touch targets; pills absent; marquee still renders (masked).
- [ ] Sidebar toggle still persists state across reload (localStorage) and reflects on next visit.
- [ ] Toast flows: validate errors surface as error toasts; messages still appear in `#messageArea` (message area unchanged).

---

## Scoring

```
score = 0.30·AnimationFidelity + 0.25·Design + 0.25·Craft + 0.20·Functionality
```

Category grade bands: 9–10 exceptional / on-spec; 7–8 solid with minor gaps (e.g. one pass band slightly missed); 5–6 major gaps (feature missing, wrong mechanism, timing way off); < 5 fails the intent of the brief.

**Pass: weighted score ≥ 8.0 AND no category < 5 AND all hard gates.** If the pass is not met, `gan-harness/feedback/feedback-NNN.md` must include: per-check PASS/FAIL with measured values (sampled widths, durations, transform matrices, opacities), the four category scores + weighted total, the prioritized fix list (ordered by score impact), and the exact reproduction commands. If it passes, record the final evidence and scores in the feedback file and mark the loop complete for the parent agent.
