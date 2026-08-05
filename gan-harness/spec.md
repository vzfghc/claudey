# Product Specification: Firecrawl Animation Patterns for the Claudey Admin

> Generated from brief: "Implement the animation patterns documented in docs/firecrawl-animation-reference.md into the Claudey admin UI at src/claudey/api/admin_static/ (index.html, admin.css, admin.js — vanilla HTML/CSS/JS, no build step, no framework)."

## Vision

The Claudey admin becomes *physically satisfying* to use: a sidebar that glides between full and rail with a snappy-ease tween (not a CSS transition), a single sliding heat-orange pill that glides between nav items, buttons that lift on hover and sink on press with layered shadows and a sheen overlay, sonner-style toasts that scale in and can be swiped away, and a JS-driven logo marquee of all 32 supported providers. Everything is gated behind `prefers-reduced-motion` (firecrawl's `motion-safe` pattern), and every accessibility attribute (`aria-expanded`/`aria-controls` on `#sidebarToggle`, `aria-current`, focus outlines, `inert` handling) survives intact. The app stays vanilla HTML/CSS/JS served from `/admin/assets/` — no build step, no framework, no external CDN at runtime.

## Design Direction

- **Color palette**: reuse existing tokens exactly (`admin.css` `:root` + dark-theme override). Accent is heat-orange `--heat-100: #FA5D19` / `--heat-80: #E04D0A`; tints `--heat-10: rgba(250,93,25,0.10)` (active pill bg), `--heat-35: rgba(250,93,25,0.35)` (active pill border). Hover pill = neutral gray `rgba(28,25,23,0.04)`. Button shadows use heat/neutral alphas only (see Feature 3 for exact values). No new hues; no gradients beyond the button sheen (`white → transparent`) and the marquee edge mask.
- **Typography**: unchanged (`--font-sans`, `--font-rounded`, `--font-mono`). The marquee caption uses `--font-mono` uppercase small caps to match existing section labels.
- **Layout philosophy**: keep the proven shell (sticky sidebar + `auto minmax(0,1fr)` grid + fixed action bar). The sidebar collapses to a **64px rail** (from today's 76px) and expands to **256px** (from today's 260px), per the firecrawl reference. Main content reflows every tween frame via the grid's `auto` column — no JS needed there.
- **Visual identity**: one gliding heat pill + one gliding gray hover pill replace per-item highlight boxes in the nav (firecrawl §4.3); physical buttons via layered shadows + sheen (firecrawl §5.2); a masked, two-track logo marquee at the top of the Providers view. The heat pill and the marquee are the two signature pieces that make this read "firecrawl-grade polish" rather than "class-toggle UI".
- **Inspiration**: firecrawl.dev dashboard sidebar (tween recipe, pills, buttons), Sonner toast system (enter/exit scale, swipe-out, snap-back), Magic UI marquee.

### Anti-AI-slop directives (hard requirements)
1. No CSS `transition: width` or `transition: left` anywhere for the sidebar/action-bar — the tween must be JS-driven per-frame inline styles (the evaluator checks `el.style.width` is non-empty mid-tween and `getAnimations()` is not the mechanism).
2. No per-item nav highlight backgrounds at desktop widths — exactly one shared active pill and one shared hover pill. No `::before` indicator bars.
3. No gradient abuse: the only gradients allowed are the button sheen overlay and the marquee `mask-image` edge fade.
4. No new keyframes that run unconditionally — every decorative animation gates behind `prefers-reduced-motion` (the existing global `@media (prefers-reduced-motion: reduce)` block in `admin.css` already zeroes durations; JS must additionally not run tween/marquee loops).
5. No emoji icons, no new libraries, no CDN requests at runtime (marquee logos are served from `/admin/assets/logos/`).
6. Do not remove or rename any existing element id, class, or aria attribute. `#sidebarToggle`, `#sectionNav`, `.nav-link`, `.nav-icon`, `.nav-label`, `.brand-text`, `.toast`, `#toastContainer` all keep their names.

## Features (prioritized)

### Feature 1 — JS-tweened sidebar collapse/expand (P0, firecrawl §4.1–4.2)

**What**: Replace the CSS-transition collapse (`body.sidebar-collapsed .sidebar { width: 76px }`) with a per-frame rAF tween that writes inline `width`, `padding-left`, `padding-right` on `aside.sidebar`, plus a CSS custom property `--sidebar-w` on `<html>` that the fixed `.action-bar` consumes. Labels (`.brand-text`, `.nav-label`) fade out via inline `opacity` as the width shrinks and are visually unmounted (`body.sidebar-rail` class) only after the tween finishes; they fade back in on expand. Icons end up centered in the rail.

**Dimensions and timing** (firecrawl-measured, adapted):
- Expanded: `width: 256px; padding: 24px 20px;` (content 216px)
- Collapsed rail: `width: 64px; padding: 24px 12px;` (content 40px)
- Collapse tween: **350ms**, easing `cubic-bezier(0.22, 1, 0.36, 1)` (easeOutQuint — snappy start, gentle settle)
- Expand tween: **220ms**, same easing
- Label fade window: `opacity = clamp((width - 120) / (256 - 120), 0, 1)` — labels fully invisible once width < 120px (~71% through the collapse), fully visible again ≥ 236px on expand.

**Implementation**:

*New file `src/claudey/api/admin_static/admin-animations.js`* (ES module, `type="module"`, loaded after `admin.js`). Top-level structure (module scope, ~380 lines total):

```js
// 0. Guards & constants
const REDUCED_MOTION = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const DESKTOP = window.matchMedia("(min-width: 901px)");
const SIDEBAR_W = { expanded: 256, collapsed: 64, padExpanded: 20, padCollapsed: 12,
                    collapseMs: 350, expandMs: 220,
                    ease: "cubic-bezier(0.22, 1, 0.36, 1)" };
```

- `easeOutQuint(t) = 1 - Math.pow(1 - t, 5)` (JS-side; used only for progress math on label opacity if needed — the CSS `transition` is NOT used for width).
- `tweenSidebar(targetCollapsed)` — single rAF loop, **time-based progress** (`progress = (now - start) / duration`, clamped) so dropped frames never stall it:
  - Cancel any running tween first (`cancelAnimationFrame`).
  - Every frame write: `sidebar.style.width`, `sidebar.style.paddingLeft/Right` (lerped with easing), `document.documentElement.style.setProperty("--sidebar-w", width + "px")`, and label opacity `clamp((w - 120) / 136, 0, 1)` to every `.nav-label` and `.brand-text`.
  - On completion: **collapse** → keep inline styles (64px/12px/opacity 0), add `sidebar-rail` class to `document.body`. **Expand** → remove `sidebar-rail` at tween *start*, clear all inline styles at tween *end* (`el.style.width = ""` etc., so CSS defaults own the final state).
- `window.__sidebarTweenToggle` — the click entry point:
  - If `REDUCED_MOTION || !DESKTOP.matches` → call `window.applySidebarCollapsed(!collapsed)` and return (instant; no tween). Also snap inline width/padding/`--sidebar-w`/label opacity synchronously so CSS end-state is consistent.
  - Else: call `window.applySidebarCollapsed(!collapsed)` FIRST (state, `aria-expanded`, `aria-label`, title, localStorage, mobile `inert` — all unchanged, owned by `admin.js`), then start `tweenSidebar` in the new direction.
- Init (runs at module load, after `admin.js` has executed): if `document.body.classList.contains("sidebar-collapsed")` at load, snap to rail instantly (inline 64px/12px, `--sidebar-w: 64px`, label opacity 0, add `sidebar-rail`).
- `DESKTOP` `change` listener: crossing 900px mid-tween → cancel tween and snap to the class-based end state instantly (mirrors `admin.js`'s existing `mobileQuery` handling for `inert`).
- `prefers-reduced-motion` `change` listener: cancel running tween, snap; stop/start marquee loop.

*Edit `admin.js`* (surgical, ≤10 lines): the existing sidebar click listener becomes

```js
sidebarToggle.addEventListener("click", () => {
  if (window.__sidebarTweenToggle) { window.__sidebarTweenToggle(); return; }
  applySidebarCollapsed(!document.body.classList.contains("sidebar-collapsed"));
});
```

*Edit `admin.css`* (surgical, see File Plan): remove `transition: width ...` from `.sidebar`; change `body.sidebar-collapsed .sidebar { width: 76px; ... }` → `width: 64px; padding: 24px 12px;` (kept as a no-JS fallback) and **move all other collapsed visual rules** (`brand-text` hide, `nav-link` justify/padding, `nav-label` width 0, footer centering) from `body.sidebar-collapsed` to `body.sidebar-rail`; change `.action-bar` to `left: var(--sidebar-w, 256px)` and drop its `transition: left`.

*New file `admin-animations.css`*: `:root { --sidebar-w: 256px; }`; `.sidebar-rail` visual rules live in the `@media (min-width: 901px)` block (mobile keeps the existing nav `max-height` collapse); `.nav-label { transition: none }` at ≥901px so per-frame inline opacity isn't lagged by a CSS transition.

**Toggle chevron**: keep the single chevron + its 180° rotation on `body.sidebar-collapsed` (existing behavior preserved); set `transition: transform 0.35s` (aligned with collapse duration) and add `active:scale(0.98)` press feedback with 50ms transition (firecrawl §4.4).

**Edge cases**: rapid double-click mid-tween → cancel and reverse from the *current* inline width; tab hidden mid-tween → time-based progress resumes correctly on `visibilitychange` (rAF auto-resumes); window resize across 900px → snap (above); reduced motion → instant jump, no intermediate frames; initial load with `localStorage["claudey.sidebar.collapsed"]` → instant rail, no flash animation.

**Acceptance criteria**:
1. Click collapses with ≥10 distinct sampled widths between 256 and 64, tween duration 250–500ms, width at t≈100ms < 160px (snappy start), and `sidebar.style.width` non-empty mid-tween.
2. `.brand-text` and `.nav-label` opacity reach 0 during the tween; final rail has icons centered (nav-link `justify-content: center`, padding `10px 0`, gap 0) via `body.sidebar-rail`.
3. `#sidebarToggle` aria-expanded flips to `"false"` at click time (before tween completes), `aria-controls="sectionNav"` intact; `title`/`aria-label` flip.
4. Expand restores 256px and clears inline styles; labels fade back in.
5. `body.sidebar-rail` and `body.sidebar-collapsed` are both absent in mobile viewport; mobile collapse (nav `max-height`) still works.
6. Reduced motion: single jump to 64px, no intermediate frames; expand likewise.

### Feature 2 — Sliding active/hover pills in #sectionNav (P0, firecrawl §4.3)

**What**: Replace per-item `.nav-link.active` background/border and the `::before` bar at desktop widths with two shared absolute-positioned pills inside the (now `position: relative`) `#sectionNav`: a heat-tinted **active pill** that translates to the current view, and a gray **hover pill** (opacity 0 idle) that slides to the hovered item. Both animate via `transition: transform 0.2s cubic-bezier(0.22,1,0.36,1), opacity 0.15s ease` (firecrawl uses `transition: all`; transform+opacity is the same glide, cheaper).

**Implementation** (in `admin-animations.js`, zero changes to `admin.js`):
- Pills are created by a `MutationObserver` on `#sectionNav` (childList + subtree attributes, `attributeFilter: ["class"]`):
  - On childList mutation (nav rebuilt by `renderNav`): remove stale pills, append `<div class="nav-pill nav-pill-active" aria-hidden="true"></div>` and `<div class="nav-pill nav-pill-hover" aria-hidden="true"></div>` to the nav; set active pill `transform: translateY(index * 46px)` (pitch = 40px item + 6px grid gap; `--nav-index` is already set on each link but index from DOM order is fine).
  - On class attribute mutation (active view switched by `setActiveView`): recompute active index from `.nav-link.active` and set `transform` — the CSS transition glides it.
- Pills use `position: absolute; left: 0; right: 0; top: 0; height: 40px; pointer-events: none; z-index: 0;` and nav-links get `position: relative; z-index: 1;` so hover/clicks pass to links (grid absolute-positioned children are out of flow — safe).
- Initial render must NOT animate: pills get transform set before the nav has a `nav-pills-ready` class; add `nav-pills-ready` after two rAFs (CSS: `.section-nav:not(.nav-pills-ready) .nav-pill { transition: none }`).
- Hover pill visibility: `#sectionNav:hover .nav-pill-hover { opacity: 1 }` (pure CSS; the pill translates because a `pointermove` listener on the nav sets `translateY(hoveredIndex * 46px)` from `event.target.closest(".nav-link")`; on mouseleave → opacity 0). Keyboard focus does NOT move the hover pill (active pill covers keyboard state).

**CSS** (`admin-animations.css`, ≥901px only):
- `.nav-pill-active { background: var(--accent-muted); border: 1px solid var(--accent-border); box-shadow: var(--shadow-sm); opacity: 1; }`
- `.nav-pill-hover { background: rgba(28, 25, 23, 0.04); opacity: 0; }`
- At ≥901px: `.nav-link { background: transparent; border-color: transparent; }`, `.nav-link:hover { background: transparent; }` (hover pill carries the highlight; text still darkens), `.nav-link.active { background: transparent; border-color: transparent; color: var(--accent); }`, and `.nav-link::before { display: none; }`.
- Move the existing `.nav-link.active` bg/border/shadow + `::before` rules and `.nav-link:hover` background into the existing `@media (max-width: 900px)` block so mobile keeps per-item highlights (no pills there).
- Pills work identically in rail mode (nav width shrinks; pill width follows `left/right: 0`; pitch unchanged).

**Edge cases**: nav re-render (only at initial load — `renderNav` runs once) rebuilds pills; view switch mid-hover → active pill still correct (index recomputed from DOM); reduced motion → the global 0.01ms rule makes pill jumps instant (correct).

**Acceptance criteria**:
1. Exactly one `.nav-pill-active` and one `.nav-pill-hover` in `#sectionNav` at ≥901px; zero in mobile viewport.
2. Hovering the 2nd nav-link: hover pill opacity ≈ 1, `transform` translateY ≈ 46px; mouse leaves nav → opacity 0.
3. Clicking the 2nd link: active pill translateY transitions from 0 to 46px (≥2 distinct sampled values mid-flight, ≤300ms), final background is the heat tint (`rgba(250,93,25,0.10)`-family), `.nav-link.active` computed background is transparent, `aria-current="page"` moves to the new link.
4. Clicking a 3rd link glides the pill again; switching back glides back.

### Feature 3 — Lift-and-press buttons (P0, firecrawl §5.2)

**What**: `.primary-button` and `.secondary-button` become physical: layered box-shadows (inset bottom glow + ambient + contact), a white→transparent sheen `::before` overlay (opacity 0.06 → 0.08 on hover, 0 on press with 50ms), shadow lift on hover, `scale(0.995)` press with 50ms transitions, shadows contract on press.

**Exact values** (primary — heat; secondary — neutral):

| State | Primary box-shadow | Secondary box-shadow |
|---|---|---|
| Base | `inset 0 -6px 12px rgba(224,77,10,0.25), 0 2px 4px rgba(250,93,25,0.12), 0 1px 1px rgba(250,93,25,0.12)` | `inset 0 -6px 12px rgba(28,25,23,0.05), 0 2px 4px rgba(28,25,23,0.06), 0 1px 1px rgba(28,25,23,0.05)` |
| Hover | `inset 0 -6px 12px rgba(224,77,10,0.25), 0 4px 8px rgba(250,93,25,0.16), 0 1px 1px rgba(250,93,25,0.12), 0 0 0 1px rgba(250,93,25,0.12)` | `inset 0 -6px 12px rgba(28,25,23,0.05), 0 4px 8px rgba(28,25,23,0.09), 0 1px 1px rgba(28,25,23,0.05), 0 0 0 1px rgba(28,25,23,0.06)` |
| Active | `inset 0 -3px 6px rgba(224,77,10,0.30), 0 1px 2px rgba(250,93,25,0.08)` | `inset 0 -3px 6px rgba(28,25,23,0.08), 0 1px 2px rgba(28,25,23,0.05)` |
| Disabled | `none` (+ existing disabled colors) | `none` |

- Sheen: `.primary-button::before, .secondary-button::before { content: ""; position: absolute; inset: 0; border-radius: inherit; background: linear-gradient(180deg, rgba(255,255,255,0.9), rgba(255,255,255,0)); opacity: 0.06; transition: opacity 0.2s ease; pointer-events: none; }` — hover → `0.08`, active → `0` with `transition: opacity 0.05s ease`.
- Buttons need `position: relative; overflow: hidden;` (clips the sheen at the rounded corners; does not clip the button's own focus outline).
- Transitions: base `transition: background-color 0.2s var(--ease-default), border-color 0.2s var(--ease-default), color 0.2s var(--ease-default), transform 0.1s var(--ease-default), box-shadow 0.1s var(--ease-default)`; `:active` overrides `transition-duration: ..., 0.05s, 0.05s` for transform/box-shadow (press is snappier, firecrawl).
- Press scale: primary/secondary `transform: scale(0.995)` on `:active:not(:disabled)`; **edit** the existing grouped rule in `admin.css` (`.primary-button:not(:disabled):active, .secondary-button:not(:disabled):active, .test-button:not(:disabled):active { transform: scale(0.98) }`) to keep only `.test-button` at 0.98 and move primary/secondary to the new file at 0.995.
- Keep existing hover background changes (primary → `var(--heat-80)`, secondary → `var(--panel-strong)`) — shadow lift is additive.
- `.card-configure`, `.ghost-button`, `.test-button`, `.configured-badge`, `.segment`, `.nav-link` are NOT lift-and-press (ghost/segments stay flat; `.card-configure` keeps its heat hover but inherits the secondary layered shadow via the class it already uses).

**Acceptance criteria**:
1. `#validateButton` (secondary, always enabled): computed box-shadow contains `inset 0 -6px 12px`; hovering changes the ambient shadow (blur 4px→8px); `::before` opacity 0.06→0.08.
2. `#applyButton` (primary, after dirtying a field): on `pointerdown` (no release) computed `transform` ≈ scale(0.995), `::before` opacity 0, shadow contracted — all within ~100ms of press.
3. Disabled primary button has `box-shadow: none` and sheen opacity 0.
4. Ghost buttons show no layered shadows (regression: flat look preserved).

### Feature 4 — Sonner-style toasts (P1, firecrawl §2 + §5.2 loading)

**What**: Upgrade `#toastContainer` behavior: enter = fade + scale 0.8→1 (0.18s), exit = fade + scale 0.9 + translateY(-6px) (0.18s), horizontal swipe-to-dismiss with snap-back (springy `cubic-bezier(0.34,1.56,0.64,1)` return), and a loading toast variant with a spinner for in-flight actions.

**Implementation**:
- *CSS overrides in `admin-animations.css`* (same specificity, later file wins):
  - `.toast { animation: sonner-in 0.18s cubic-bezier(0.22,1,0.36,1) backwards; }` with `@keyframes sonner-in { from { opacity: 0; transform: scale(0.8); } to { opacity: 1; transform: scale(1); } }` (replaces `toast-in`).
  - `.toast-leaving { opacity: 0; transform: scale(0.9) translateY(-6px); transition: opacity 0.18s ease, transform 0.18s ease; }` (replaces the old translateX exit).
  - `.toast.toast-loading .toast-icon { animation: toast-spin 0.8s linear infinite; }` + `@keyframes toast-spin { to { transform: rotate(360deg); } }`.
  - `.toast.swiping { transition: none; }` and `.toast.snap-back { transition: transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1), opacity 0.15s ease; }`.
- *Swipe-out* in `admin-animations.js` via **pointer-event delegation on `#toastContainer`** (works for toasts added later; `admin.js` untouched for this): `pointerdown` on a `.toast` → record start x/y, add `.swiping`; `pointermove` → `transform: translateX(dx)` + `opacity: 1 - min(|dx| / 220, 0.6)` inline; `pointerup` → if `|dx| > 70` (or drag velocity high) dismiss toward that side (`transition: 0.18s; transform: translateX(dx + sign(dx) * 120px); opacity: 0` → remove after 180ms), else snap back (clear inline transform, add `.snap-back` for the springy return, remove after 300ms). Suppress the toast's click-to-dismiss when a drag occurred (`dx > 10`). Dragging only if the toast lacks `.toast-leaving`. Touch works via pointer events (set `touch-action: pan-y` on `.toast` so vertical scrolling still works — horizontal drags are intercepted).
- *Loading toast* in `admin.js` (surgical, ~12 lines):
  - `showToast`: at the top, `container.querySelector(".toast-loading")?.remove();` (a new toast replaces a pending one — sonner behavior).
  - Icon selection gains `kind === "loading"` → spinner SVG (`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" aria-hidden="true"><path d="M12 3a9 9 0 1 0 9 9"/></svg>`); class becomes `toast toast-loading`.
  - Loading toasts skip the 4s auto-dismiss timer (only `ok`/`error`/`warn`/plain get it) — they resolve when the next toast replaces them or the page navigates. Click-dismiss stays for all kinds.
  - Wire in-flight actions to loading toasts: `restartServer` success → `showMessage("Restarting server...", "loading")` (was `"ok"`); `apply()` automatic-restart branch → `showMessage("Applied. Restarting server...", "loading")`; `refreshModelOptions` start → `showMessage("Refreshing models...", "loading")` (resolves when the ok/warn toast replaces it).
- `aria-live="polite"` on `#toastContainer` and `role="status"` on toasts stay untouched.

**Edge cases**: toast auto-dismisses at 4s while being dragged — accepted (timer closure in `admin.js`; the `.toast-leaving` guard prevents fighting a removal already in progress); rapid successive toasts replace loading state correctly; swipe on touch doesn't break vertical page scroll (`touch-action: pan-y`); reduced motion → global 0.01ms rule makes enter/exit instant (correct sonner behavior under `motion-safe`).

**Acceptance criteria**:
1. New toast: computed transform scale starts < 0.85 and settles at 1 (sample within first 250ms); opacity 0→1.
2. Click-to-dismiss: `.toast-leaving` added, element removed from DOM ≤ 400ms later.
3. Drag 120px right + release → toast follows pointer (translateX ≈ 120 during drag, opacity < 1) and is removed ≤ 400ms after release.
4. Drag 40px + release → toast springs back (transform returns to `none`) and STAYS in DOM.
5. Refresh models (safe button in the Model Config view) → `.toast-loading` appears with a spinning icon and no auto-dismiss; completes into an ok toast.
6. `#toastContainer` retains `aria-live="polite"`.

### Feature 5 — JS-driven logo marquee (P1, firecrawl §3 "People love building")

**What**: An infinite-scroll marquee strip at the top of the Providers view (`#view-providers`, first child, above `#onboardingCard`): two mirrored tracks (row A scrolls left, row B scrolls right), each containing the full logo set repeated twice for a seamless loop, driven by a rAF `translateX` tween (~32px/s, firecrawl-measured), paused on hover, edge-masked, `aria-hidden`, gated behind reduced motion.

**Implementation**:
- *`index.html`*: inside `#view-providers`, before `#onboardingCard`:
  ```html
  <section class="provider-marquee" aria-label="All supported providers">
    <p class="marquee-caption">All supported providers</p>
    <div class="marquee" aria-hidden="true">
      <div class="marquee-track marquee-track-a"></div>
      <div class="marquee-track marquee-track-b"></div>
    </div>
  </section>
  ```
- *JS (module)*: `MARQUEE_LOGO_SLUGS` = the exact filenames in `src/claudey/api/admin_static/logos/` — the brief says 34, the directory currently contains **32**: `azure_openai, open_router, gemini, vertex, deepseek, mistral, mistral_codestral, opencode, opencode_go, vercel, bedrock, huggingface, cohere, github_models, wafer, kimi, kimi_code, kilo, minimax, cerebras, sambanova, fireworks, cloudflare, zai, ollama_cloud, lmstudio, llamacpp, ollama, anthropic, groq, nvidia_nim, openai`. (Generator: re-list the directory at implementation time and reconcile — use the real files; do not fabricate missing ones.)
  - `buildTrack(track)`: append each slug twice (`<img src="/admin/assets/logos/${slug}.svg" alt="" width="32" height="32" loading="lazy">`); `error` listener → `img.style.display = "none"` (no layout shift).
  - Measure half-width = `track.scrollWidth / 2` after one rAF (imgs have fixed 32px CSS size, so this is stable pre-load).
  - Loop (only if `!REDUCED_MOTION`): `trackA` offset 0 → +32px/s, wrap by subtracting half-width when ≥ half; `trackB` starts at `-half`, moves +32px/s toward 0, wraps by adding half-width when ≤ -half. Write `transform: translateX(px)` each frame. rAF stops when `document.hidden` (automatic) and on hover (module flag set by `mouseenter`/`mouseleave` on `.marquee`).
  - Reduced motion / media change: don't start the loop (static strip, offsets 0); on `prefers-reduced-motion` change to reduce → cancel loop.
- *CSS*: `.marquee { overflow: hidden; display: flex; flex-direction: column; gap: 12px; border: 1px solid var(--line); border-radius: var(--radius-lg); background: var(--panel); mask-image: linear-gradient(90deg, transparent, #000 8%, #000 92%, transparent); -webkit-mask-image: <same>; }`; `.marquee-track { display: flex; align-items: center; gap: 28px; padding: 14px; flex: none; width: max-content; will-change: transform; }`; `.marquee-track img { width: 32px; height: 32px; opacity: 0.85; }` `.marquee-track img:hover { opacity: 1; }`; caption: `font-family: var(--font-mono); font-size: 11px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; color: var(--muted); margin: 0 0 8px;`.

**Edge cases**: images still loading → fixed-size layout means no reflow; missing logo → hidden, gap remains (flex gap — acceptable); narrow viewports → mask keeps edges clean, strip scrolls as normal; reduced motion → static strip, no rAF; the marquee lives inside `#view-providers` so it hides automatically when other views are active.

**Acceptance criteria**:
1. Two tracks, each with 64 imgs (32 × 2), all served from `/admin/assets/logos/`, zero broken-image icons.
2. `transform` of track A sampled 500ms apart differs by ≈ 16px (32px/s) and x is decreasing; track B increases (mirrored).
3. Hovering `.marquee` freezes both tracks (transform stable over 400ms).
4. Reduced motion: transforms static over 600ms; no rAF loop running.
5. Strip is `aria-hidden`, caption is the only accessible text.

### Feature 6 — Reduced-motion & accessibility preservation (P0 gate)

**What**: Every decorative animation gates behind `prefers-reduced-motion` (firecrawl `motion-safe` pattern). All existing a11y attributes and behaviors survive.

**Implementation**:
- JS: sidebar tween → instant snap; marquee → static; toast swipe still works (it's an interaction, but enter/exit scale is killed by CSS); pills → CSS transitions zeroed by the existing global rule.
- Keep: `aria-expanded`/`aria-controls`/`aria-label`/`title` on `#sidebarToggle` (managed by `admin.js`'s `applySidebarCollapsed` — module must not duplicate or fight it); `aria-current="page"` on the active link; `sectionNav.inert` on mobile collapse; `role="status"` on toasts; `aria-live="polite"` on the container; focus-visible outlines; `aria-hidden` on decorative pills and the marquee.
- Nav accessibility in rail mode: `.nav-label` is `visibility: hidden` under `body.sidebar-rail` (after opacity hits 0) and each `.nav-link` keeps its `title` attribute, so the rail remains keyboard- and AT-friendly.
- The existing global `@media (prefers-reduced-motion: reduce)` block in `admin.css` (`* { animation-duration: 0.01ms !important; ... }`) stays — it zeroes any CSS animation/transition we add.

**Acceptance criteria**: (evaluator: see rubric — emulate `reducedMotion: "reduce"`, reload, verify instant sidebar jump, static marquee, no broken focus, aria intact).

## Technical Stack

- Frontend: vanilla HTML/CSS/JS (no build step, no framework, no dependencies). ES module (`type="module"`) for the new animation script — served statically like any other file (no Python changes needed; `/admin/assets/{filename}` already serves the whole directory).
- Files:
  - `src/claudey/api/admin_static/index.html` — add 2 asset links (CSS after `admin.css`, module script after `admin.js`) + marquee markup.
  - `src/claudey/api/admin_static/admin.css` — surgical edits only (list below). Stays ~1760 lines (pre-existing size; not feasible to split safely — new CSS goes to the new file).
  - `src/claudey/api/admin_static/admin-animations.css` — **new**, ~300 lines (all new rules; < 800 ✓).
  - `src/claudey/api/admin_static/admin.js` — surgical edits only, ≤ 30 lines added (sidebar hook, loading toasts, spinner icon). Stays ~1750 lines.
  - `src/claudey/api/admin_static/admin-animations.js` — **new**, ~380 lines (sidebar tween, pills, toast swipe, marquee, motion gating; < 800 ✓).
  - `tests/api/test_admin.py` — add static-assertion tests (repo convention) for the new files.
  - `pyproject.toml` — `5.9.0 → 5.10.0` (MINOR: new capability) + `uv lock` in the same commit.

### admin.css edit list (exact)
1. `.sidebar` (~line 162): change base `width: 260px` → `width: 256px` AND delete `transition: width var(--transition-normal), padding var(--transition-normal);` — JS owns width/padding (256/64 per the firecrawl reference).
2. `.section-nav` (~line 207): add `position: relative;`.
3. `.nav-link:hover` (~line 232): move `background: var(--panel-strong)` into the ≤900px media query (keep the color change at all widths).
4. `.nav-link.active` bg/border/shadow (~line 237) + `.nav-link::before` block (~line 244): move both into `@media (max-width: 900px)`.
5. `.nav-label` (~line 275): delete `transition: opacity ..., width ...` (JS drives opacity; keep `overflow: hidden; white-space: nowrap`).
6. `.action-bar` (~line 911): `left: 260px` → `left: var(--sidebar-w, 256px)`; delete `transition: left ...`.
7. Sprint-5 block `@media (min-width: 901px)` (~line 1618): `body.sidebar-collapsed .sidebar { width: 76px; padding: 24px 12px }` → `width: 64px; padding: 24px 12px` kept as fallback; rename the selector group for the other rules (`brand-text`, `nav-link`, `nav-label`, `sidebar-footer`) from `body.sidebar-collapsed` to `body.sidebar-rail`; delete `body.sidebar-collapsed .action-bar { left: 76px }` (var-driven now).
8. Grouped `:active` scale rule (~line 1671): remove `.primary-button`/`.secondary-button` from the 0.98 rule (keeps only `.test-button`).
9. Mobile `@media (max-width: 900px)` `.nav-link`/`.nav-label` rules (existing) — keep as-is; they now coexist with the moved per-item highlight rules.

## Evaluation Criteria

See `gan-harness/eval-rubric.md` for the scored rubric. Summary: **Hard Gate** (blockers ⇒ 0) — server serves the UI, `./scripts/ci.sh` passes, semver bumped 5.10.0 + `uv.lock` in sync, no broken assets, aria attributes intact. Then four weighted axes (each 0–10):

| Axis | Weight | What is scored |
|---|---|---|
| Animation Fidelity | 0.30 | Sidebar tween frames/timing/easing, pill glide, button lift/press timing, toast enter/exit/swipe, marquee motion, reduced-motion handling |
| Design | 0.25 | Visual polish vs the firecrawl reference: pill system, physical buttons, masked marquee, no slop, cohesion with the existing warm-light theme |
| Craft | 0.25 | Implementation quality: file organization, no dead code, immutability, error handling, edge cases, motion-safe pattern, test coverage added |
| Functionality | 0.20 | All existing admin flows still work (view switching, forms, dirty state, keyboard shortcuts, mobile layout, server status) |

**Pass threshold**: weighted score ≥ 8.0 AND no axis < 5 AND all hard gates pass. Loop: evaluator writes evidence + feedback to `gan-harness/feedback/feedback-NNN.md`; generator iterates until threshold met.

## Sprint Plan

### Sprint 1: Foundation & Sidebar Tween
- Goals: file scaffolding, admin.css surgical edits, sidebar JS tween + rail mode + motion gating, admin.js hook.
- Features: #1 (sidebar), #6 (motion/a11y baseline for the sidebar).
- Definition of done: sidebar collapses/expands via per-frame inline width tween with measured easing; rail mode centers icons; labels fade-then-hide; `aria-expanded`/`aria-controls` intact; reduced-motion jumps instantly; `--sidebar-w` drives the action bar; CI green with new static tests.

### Sprint 2: Sliding Pills & Lift-and-Press Buttons
- Goals: shared-pill nav system; physical button states.
- Features: #2, #3.
- Definition of done: one active + one hover pill glide between items with correct pitch (46px); per-item highlights only ≤900px; buttons show layered shadows, sheen 0.06→0.08, scale 0.995 press, 50ms active transitions; ghost buttons unchanged.

### Sprint 3: Sonner Toasts & Logo Marquee
- Goals: toast enter/exit/swipe/loading; two-track marquee.
- Features: #4, #5.
- Definition of done: scale-fade toasts with swipe-out + snap-back; loading spinner toast wired into restart/apply/refresh flows; 32-logo mirrored marquee with hover-pause and mask; reduced-motion static.

### Sprint 4: Verify, Test & Ship
- Goals: live Playwright verification per `eval-rubric.md`, fix loop with the Evaluator, ship.
- Features: all; final polish pass (timing tuning, edge cases).
- Definition of done: evaluator weighted score ≥ 8.0 with no axis < 5; `./scripts/ci.sh` green; `pyproject.toml` → `5.10.0` + `uv lock` in the same commit; conventional commit(s) on `main` (e.g. `feat: firecrawl-style admin animations (v5.10.0)`); `gan-harness/generator-state.md` updated.

## Constraints & Conventions (from CLAUDE.md / brief)
- Vanilla HTML/CSS/JS only — no build step, no framework, no runtime CDN.
- Preserve ALL existing functionality and accessibility attributes; do not remove existing ids/classes/aria.
- Files cohesive: new files < 800 lines; `admin.css`/`admin.js` receive only surgical edits (no wholesale refactors).
- No `# type: ignore`, no `from __future__ import annotations` (N/A for JS, but keep Python edits clean), no `console.log`.
- Immutability: no mutation of existing state objects in `admin.js`; module code creates new DOM nodes, never rewrites existing handlers.
- Run `./scripts/ci.sh` (ruff format, ruff check, ty, pytest) before pushing; add tests for the new files (static assertions in `tests/api/test_admin.py` per existing convention: `test_admin_static_*`).
- Semver: production change (files under `src/claudey/api/`) → MINOR bump `5.9.0 → 5.10.0` with `uv lock` in the same commit.
- Evaluation runs against the live server: `uv run hans-server` (background) → http://127.0.0.1:8082/admin (port from generator-state; verify with `claudey doctor` if needed).
- Commit with conventional commits when the loop passes.
