# Generator State — Iteration 002

## What Was Built

Iteration 2 implements all 4 items from the design review (`gan-harness/feedback/feedback-001.md`) on top of the iteration-1 animation layer, still vanilla HTML/CSS/JS, no new libraries, no runtime CDN:

- **Item 1 — Active nav pill**: `.nav-pill-active` no longer has `border: 1px solid var(--accent-border)`; it is now `background: var(--accent-muted); border-radius: 999px; box-shadow: var(--shadow-sm);`. `.nav-label` font-weight reduced to 400 (base rule in admin.css, shared by idle and active states). All existing ids/classes/aria preserved.
- **Item 2 — Sidebar hover-to-expand**: the rail now expands on cursor enter and collapses on leave (mouseenter/mouseleave in admin-animations.js) using the existing per-frame tween (expand 220ms, collapse 350ms, easeOutQuint). `#sidebarToggle` click remains the pin/unpin override, still owned by admin.js (`applySidebarCollapsed`: class + localStorage + inert + aria). Hover-peek is purely visual: it tweens inline width/padding + `--sidebar-w` + label fade + `body.sidebar-rail`, and mirrors the visually expanded state into `aria-expanded` on the toggle; it never touches `sidebar-collapsed`, localStorage, or inert. Edge cases handled: same-target tween guard (`sidebarTweenTarget`) so pin-click-then-leave can't restart the collapse tween; mid-tween reversal resumes from `parseFloat(sidebar.style.width)`; reduced-motion/`<901px` snaps instead of tweens; pinned state (class removed) never collapses on hover-out; media-query changes cancel tweens and call `restoreSidebarAria()`. Pin label/aria-label updated by admin.js to "Pin sidebar open"/"Unpin sidebar".
- **Item 3 — Buttons**: lift-and-press (layered shadows, `::before` sheen, `scale(0.995)`, shadow-lift hover) removed from admin-animations.css; primary/secondary/test buttons are back to the original pre-iteration-1 flat styles (base rules in admin.css never changed; the grouped `:active` rule restores the shared `scale(0.98)` press for all three). The heat style applies ONLY to `.card-configure:hover:not(:disabled)` with the exact CSS from the review (`background: #ff4c00` + the 5-layer box-shadow stack + ~0.2s transition). All other buttons stay flat.
- **Item 4 — Flow diagram**: the logo marquee is gone (markup, CSS, JS, and all tests). `#view-providers` opens with a firecrawl-style `.provider-flow` section: `.flow-caption` (mono small caps, the only accessible text) + `aria-hidden` `.flow-diagram` with three node cards ("You" avatar, "Claudey" brand mark, "Providers & models" database icon) joined by two connectors. Each card: border-radius 16px, 1px faint inset border via `::before`, padding 8px, inner 96x96 node with 4 corner dots + faint center grid cross, layered subtle drop shadows, `position: relative; z-index: 1`. Each node figure carries a spinning heat-orange (`#FA5D19`) 270-degree SVG arc (1s linear). Connectors are `flex: 1` columns with a dashed arrow SVG and two spinning rings (1s heat arc + 0.9s reverse orbit). Max-width 704px, centered, column-stacked below 600px (arrow rotates 90deg). All loops gated behind `prefers-reduced-motion` (no-preference wrapper + the universal reduced-motion block in admin.css). `logos/` untouched.

## What Changed This Iteration

- `src/claudey/api/admin_static/admin-animations.css`: nav-pill-active restyle; lift-and-press section replaced with the `.card-configure` heat-on-hover rule; marquee section replaced with the full flow-diagram CSS (cards, node dots/cross, arcs, rings, arrow, responsive stack, dark-theme overrides).
- `src/claudey/api/admin_static/admin-animations.js`: marquee constants/JS removed; added sidebar hover-peek section 1b (mouseenter/mouseleave, `peekSidebar`, `isSidebarCollapsed`); `tweenSidebar` gained the same-target guard + `sidebarTweenTarget`; media-query handlers now `restoreSidebarAria()` + `cancelSidebarTween()`.
- `src/claudey/api/admin_static/admin.css`: `.nav-label` font-weight 400; lone `.test-button` `:active` rule grouped with primary/secondary (`scale(0.98)`).
- `src/claudey/api/admin_static/admin.js`: `applySidebarCollapsed` now writes aria-expanded, pin/unpin aria-label and title on the toggle.
- `src/claudey/api/admin_static/index.html`: `#sidebarToggle` initial attrs use pin wording; marquee markup replaced by the `.provider-flow` section (3 flow-cards, 2 connectors, caption).
- `tests/api/test_admin.py`: marquee tests converted to flow-diagram contract tests; new `test_admin_static_sidebar_hover_peek`; button test renamed to assert flat buttons + heat-only-on-configure with the exact review CSS; a11y test asserts module-owned peek aria + `restoreSidebarAria`.
- Version: stays `5.10.0` (iter-1 bump; design-review polish, no new capability) — `pyproject.toml`/`uv.lock` untouched and in sync.

## Known Issues

- Hover-peek and the pin button are both bound to the same `aria-expanded` attribute; a peek that ends with the cursor still inside while the media query flips to reduced-motion is reconciled by the `motionQuery` change handler (`restoreSidebarAria` + snap). No unresolved issues known.
- The flow diagram is `aria-hidden` (decorative); the caption carries the accessible text. If the product wants the diagram announced, that would need an explicit description — flagged for the evaluator.

## Dev Server

- URL: http://127.0.0.1:8082/admin
- Status: running (no restart needed this iteration — static assets are served from disk; curl verified /admin, /admin/assets/admin-animations.js, /admin/assets/admin-animations.css all 200)
- Command: `uv run hans-server` (background, log at /tmp/claudey-admin-server.log)
